from fastapi import APIRouter, HTTPException

from app.data import bmc_gis
from app.data import imd
from app.historical.events import list_events
from app.historical.replay import load_replay
from app.models.flood_model import predict

router = APIRouter(prefix="/data", tags=["real-data"])


@router.get("/bmc/flooding-spots")
async def bmc_flooding_spots():
    return await bmc_gis.get_flooding_spots()


@router.get("/bmc/flow-sensors")
async def bmc_flow_sensors():
    return await bmc_gis.get_flow_level_sensors()


@router.get("/bmc/drains")
async def bmc_drains():
    return await bmc_gis.get_storm_water_drains()


@router.get("/bmc/manholes")
async def bmc_manholes():
    return await bmc_gis.get_storm_water_manholes()


@router.get("/bmc/wards")
async def bmc_wards():
    return await bmc_gis.get_wards()


@router.get("/imd/urban-source")
async def imd_urban_source():
    html = await imd.fetch_urban_page()
    return {
        "source": imd.IMD_URBAN,
        "retrieved": True,
        "html_length": len(html),
        "note": "Use the official page as the source of current urban observations; do not invent missing station values.",
    }


@router.get("/historical/events")
def historical_events():
    return list_events()


@router.get("/historical/{event_id}/replay")
def historical_replay(event_id: str):
    try:
        return load_replay(event_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown historical event")


@router.post("/risk")
def risk_prediction(features: dict):
    return predict(features)
