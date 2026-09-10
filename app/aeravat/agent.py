from app.aeravat.tools import AeravatTools
from app.aeravat.retrieval import retrieve

async def chat(message, db, latitude=None, longitude=None):
    tools = AeravatTools(db); m = message.lower()
    rows = await tools.current_risk()
    if any(k in m for k in ["most critical", "highest risk", "worst area", "critical area"]):
        if not rows:
            return {"answer": "No spatial risk cells are available yet. Ingest current observations and base layers first.", "sources": [], "map_action": None, "proposed_actions": []}
        z = max(rows, key=lambda x: x["score"])
        return {"answer": f"The highest-risk mapped cell is {z['score']:.0f}/100 ({z['level'].upper()}). {', '.join(z['drivers'])}.",
                "sources": ["INDRA spatial risk model"],
                "map_action": {"type": "focus_coordinate", "latitude": z["latitude"], "longitude": z["longitude"]},
                "proposed_actions": z["recommended_actions"]}
    if "drain" in m or "bottleneck" in m or "manhole" in m:
        n = tools.bottlenecks()
        return {"answer": f"I found {len(n)} high-stress drainage assets in the loaded BMC network." + (f" Highest load is {n[0]['utilization_pct']:.0f}%." if n else ""),
                "sources": ["BMC GIS drainage layer"], "map_action": {"type": "highlight_drainage_assets", "assets": n}, "proposed_actions": []}
    if latitude is not None and longitude is not None:
        c = tools.nearest_cell(latitude, longitude)
        if c:
            z = tools.cell(c.id)
            return {"answer": f"This location is {z['level'].upper()} risk at {z['score']:.0f}/100. Confidence is {z['confidence']:.0f}%. Drivers: {', '.join(z['drivers'])}.",
                    "sources": ["INDRA spatial risk model", "Observed/fused rainfall data"],
                    "map_action": {"type": "focus_coordinate", "latitude": latitude, "longitude": longitude},
                    "proposed_actions": z["recommended_actions"]}
    docs = retrieve(message)
    if docs:
        return {"answer": "Based on INDRA operational guidance: " + " ".join(d["text"] for d in docs),
                "sources": [d["title"] for d in docs], "map_action": None, "proposed_actions": []}
    return {"answer": "Ask me about current risk, rainfall, drainage, historical replay, alerts or field operations.",
            "sources": ["Aeravat capability layer"], "map_action": None, "proposed_actions": []}
