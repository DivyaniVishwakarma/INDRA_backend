from fastapi import APIRouter, Depends, HTTPException
from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.db.session import get_db
from app.db.models import Alert, FieldTeam, RainfallObservation, Dispatch
from app.schemas import ChatRequest, DispatchRequest, DispatchStatusUpdate, DispatchVerify
from app.services.analytics import all_cells, node_risk_points
from app.services.events import publish
from app.aeravat.agent import chat
from datetime import datetime, timedelta, timezone
from collections import defaultdict

router = APIRouter(prefix="/api")

@router.get("/health")
def health():
    return {"status":"operational", "service":"INDRA", "assistant":"Aeravat", "architecture":"real-data-spatial"}

@router.get("/dashboard/summary")
async def summary(db: Session = Depends(get_db)):
    rows = await all_cells(db)
    alerts = db.query(Alert).filter_by(acknowledged=False).count()
    teams = db.query(FieldTeam).all()          # <-- yeh line check karo, missing na ho

    utilization_values = [
        x["drainage_utilization_pct"] for x in rows
        if x.get("drainage_utilization_pct") is not None
    ]
    avg_utilization = (
        round(sum(utilization_values) / len(utilization_values), 1)
        if utilization_values else None
    )

    return {
        "current_rainfall_mm_hr": max((x["rainfall"]["rain_60m_mm"] or 0 for x in rows), default=0),
        "areas_at_risk": sum(x["level"] in ("critical","high") for x in rows),
        "critical_zones": sum(x["level"] == "critical" for x in rows),
        "active_incidents": alerts,
        "field_teams": sum(t.status in ("en_route","on_site") for t in teams),
        "spatial_cells": len(rows),
        "drainage_utilization_pct": avg_utilization,
        "model_status": rows[0]["model"]["model_status"] if rows else "no_data",
    }

@router.get("/map/risk-zones")
async def risk_zones(db: Session = Depends(get_db)):
    return await all_cells(db)

@router.get("/map/risk-zones/nodes")     # naya, optional — street-level/granular kaam ke liye
async def risk_zones_nodes(db: Session = Depends(get_db)):
    return await node_risk_points(db)

@router.get("/alerts")
def alerts(db: Session = Depends(get_db)):
    return [{"id":a.id,"severity":a.severity,"title":a.title,"message":a.message,
             "latitude":a.latitude,"longitude":a.longitude,"acknowledged":a.acknowledged,
             "source":a.source,"created_at":a.created_at.isoformat() if a.created_at else None}
            for a in db.query(Alert).order_by(desc(Alert.created_at)).limit(50).all()]

@router.get("/operations/teams")
def teams(db: Session = Depends(get_db)):
    return [{"id":t.id,"name":t.name,"status":t.status,"latitude":t.latitude,"longitude":t.longitude} for t in db.query(FieldTeam).all()]

@router.post("/operations/dispatch")
def dispatch(body: DispatchRequest, db: Session = Depends(get_db)):
    if not body.approved: return {"status":"approval_required","message":"Human approval is required before dispatch."}
    team = db.query(FieldTeam).filter_by(id=body.team_id).first()
    if not team: raise HTTPException(404,"Team not found")
    team.status="assigned"; team.latitude=body.latitude; team.longitude=body.longitude; team.updated_at=datetime.utcnow()
    d = Dispatch(alert_id=body.alert_id, team_id=team.id, zone_name=body.zone_name,
                 task=body.task or "Field verification", status="assigned", eta_minutes=body.eta_minutes)
    db.add(d); db.commit(); db.refresh(d)
    publish("indra.operations", {"type":"team_dispatched","team_id":team.id,"dispatch_id":d.id,"latitude":body.latitude,"longitude":body.longitude})
    return {"status":"dispatched","team_id":team.id,"dispatch_id":d.id}

@router.get("/operations/dispatches")
def dispatches(db: Session = Depends(get_db)):
    rows = db.query(Dispatch).order_by(desc(Dispatch.created_at)).limit(50).all()
    return [{"id":d.id,"alert_id":d.alert_id,"team_id":d.team_id,"zone_name":d.zone_name,
             "task":d.task,"status":d.status,"eta_minutes":d.eta_minutes,
             "verification_note":d.verification_note,
             "created_at":d.created_at.isoformat() if d.created_at else None,
             "updated_at":d.updated_at.isoformat() if d.updated_at else None,
             "verified_at":d.verified_at.isoformat() if d.verified_at else None}
            for d in rows]

@router.patch("/operations/dispatch/{dispatch_id}/status")
def advance_dispatch(dispatch_id: int, body: DispatchStatusUpdate, db: Session = Depends(get_db)):
    if body.status not in ("en_route","on_site","verifying"):
        raise HTTPException(400,"Invalid status")
    d = db.query(Dispatch).filter_by(id=dispatch_id).first()
    if not d: raise HTTPException(404,"Dispatch not found")
    d.status = body.status; d.updated_at = datetime.utcnow()
    team = db.query(FieldTeam).filter_by(id=d.team_id).first()
    if team: team.status = body.status; team.updated_at = datetime.utcnow()
    db.commit()
    publish("indra.operations", {"type":"dispatch_status","dispatch_id":d.id,"status":d.status})
    return {"status":d.status,"dispatch_id":d.id}

@router.post("/operations/dispatch/{dispatch_id}/verify")
def verify_dispatch(dispatch_id: int, body: DispatchVerify, db: Session = Depends(get_db)):
    d = db.query(Dispatch).filter_by(id=dispatch_id).first()
    if not d: raise HTTPException(404,"Dispatch not found")
    now = datetime.utcnow()
    d.status = "verified"; d.verified_at = now; d.updated_at = now; d.verification_note = body.note
    team = db.query(FieldTeam).filter_by(id=d.team_id).first()
    if team: team.status = "standby"; team.updated_at = now
    if d.alert_id:
        alert = db.query(Alert).filter_by(id=d.alert_id).first()
        if alert: alert.acknowledged = True
    db.commit()
    publish("indra.operations", {"type":"dispatch_verified","dispatch_id":d.id,"alert_id":d.alert_id})
    return {"status":"verified","dispatch_id":d.id}

@router.post("/aeravat/chat")
async def aeravat(body: ChatRequest, db: Session = Depends(get_db)):
    return await chat(body.message, db, body.latitude, body.longitude)

@router.websocket("/ws")
async def ws(socket: WebSocket):
    await socket.accept()
    try:
        while True: await socket.receive_text()
    except WebSocketDisconnect: pass

@router.get("/dashboard/rainfall-trend")
def rainfall_trend(hours: int = 6, bucket_minutes: int = 15, db: Session = Depends(get_db)):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows = (
        db.query(RainfallObservation)
        .filter(RainfallObservation.timestamp >= cutoff)
        .order_by(RainfallObservation.timestamp)
        .all()
    )
    buckets: dict[datetime, list[float]] = defaultdict(list)
    for r in rows:
        ts = r.timestamp
        bucket_ts = ts.replace(minute=(ts.minute // bucket_minutes) * bucket_minutes, second=0, microsecond=0)
        buckets[bucket_ts].append(r.rain_60m_mm or 0.0)
    return [
        {"time": ts.strftime("%I:%M %p").lstrip("0"), "value": round(max(vals), 1)}
        for ts, vals in sorted(buckets.items())
    ]