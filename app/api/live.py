from app.schemas import RiskRequest
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.data import bmc_gis, imd, gpm
from app.models.features import build_features, quality
from app.models.flood_model import predict
from app.db.session import get_db
from app.intelligence.drainage_graph import build_drainage_graph

router = APIRouter(prefix="/live", tags=["live"])


@router.get("/gis")
async def gis():
    """
    Live BMC/MCGM GIS data.

    Core drainage layers are required:
      - Storm Water Drains
      - Storm Water Manholes

    Auxiliary layers are optional:
      - Flooding Spots
      - Flow Level Sensors
      - Wards
      - Mumbai Contour
    """

    try:
        # ---------------------------------------------------------
        # REQUIRED: actual BMC drainage infrastructure
        # ---------------------------------------------------------
        drains = await bmc_gis.get_storm_water_drains()
        manholes = await bmc_gis.get_storm_water_manholes()

        # ---------------------------------------------------------
        # OPTIONAL: other BMC GIS layers
        # ---------------------------------------------------------
        async def optional(fetcher):
            try:
                return await fetcher()
            except Exception as exc:
                return {
                    "type": "FeatureCollection",
                    "features": [],
                    "_available": False,
                    "_error": str(exc),
                }

        flooding_spots = await optional(
            bmc_gis.get_flooding_spots
        )

        flow_level_sensors = await optional(
            bmc_gis.get_flow_level_sensors
        )

        wards = await optional(
            bmc_gis.get_wards
        )

        contours = await optional(
            bmc_gis.get_mumbai_contour
        )

        return {
            "source": "MCGM/BMC Official GIS",
            "timestamp": datetime.now(timezone.utc).isoformat(),

            # Core infrastructure
            "storm_water_drains": drains,
            "storm_water_manholes": manholes,

            # Optional operational/context layers
            "flooding_spots": flooding_spots,
            "flow_level_sensors": flow_level_sensors,
            "wards": wards,
            "contours": contours,
        }

    except Exception as exc:
        # If actual drainage layers themselves fail,
        # the endpoint should correctly report failure.
        raise HTTPException(
            status_code=502,
            detail=f"BMC drainage GIS unavailable: {exc}",
        )


@router.get("/drainage-graph")
async def drainage_graph(db: Session = Depends(get_db)):
    """
    Real BMC manhole/drain graph (nodes + edges), with rainfall-driven
    SIMULATED capacity utilization (see build_drainage_graph docstring
    for what's real vs. simulated).
    """
    return await build_drainage_graph(db)


@router.get("/sources")
async def sources():
    return {
        "bmc_gis": bmc_gis.source_metadata(),
        "imd": imd.source_metadata(),
        "gpm": gpm.source_metadata(),
    }


@router.get("/imd")
async def imd_current():
    data = await imd.fetch_current_api()

    return {
        "available": data is not None,
        "data": data,
        "official_urban_page": imd.IMD_URBAN,
    }


@router.post("/risk")
def risk(payload: RiskRequest):
    features = build_features(**payload.model_dump())
    result = predict(features)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "features": features,
        "quality": quality(features),
        "risk": result,
    }