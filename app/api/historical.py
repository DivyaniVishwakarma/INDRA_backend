from fastapi import APIRouter, HTTPException
from app.historical.events import list_events, get_event
from app.historical.replay import load_replay
from app.data import sentinel

router = APIRouter(prefix="/historical", tags=["historical"])

@router.get("/events")
def events(): return {"events": list_events()}

@router.get("/events/{event_id}")
def event(event_id: str):
    try: return get_event(event_id)
    except KeyError: raise HTTPException(404, "Unknown historical event")

@router.get("/events/{event_id}/replay")
def replay(event_id: str):
    try: return load_replay(event_id)
    except KeyError: raise HTTPException(404, "Unknown historical event")

@router.get("/events/{event_id}/satellite-search")
async def satellite_search(event_id: str, start: str, end: str):
    try: get_event(event_id)
    except KeyError: raise HTTPException(404, "Unknown historical event")
    return await sentinel.search(start=start, end=end)

@router.get("/sources")
def historical_sources(): return {"sentinel": sentinel.source_metadata()}
