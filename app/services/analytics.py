from collections import defaultdict

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.models import DrainageAsset, RainfallObservation, SpatialCell, WaterObservation
from app.intelligence.drainage import asset_stress
from app.intelligence.drainage_graph import build_drainage_graph
from app.intelligence.nowcast import nowcast
from app.intelligence.prevention import recommendations
from app.intelligence.risk_engine import calculate_risk
from app.models.features import build_features
from app.models.flood_model import predict

# Fallback terrain characteristics used only when a manhole node has no
# nearby SpatialCell entry to borrow elevation/slope/history from. These
# are rough Mumbai-wide averages, not per-location survey data.
DEFAULT_ELEVATION_M = 6.0
DEFAULT_SLOPE_PCT = 3.0
DEFAULT_IMPERVIOUS_FRACTION = 0.65
DEFAULT_HIST_FLOOD_FREQUENCY = 0.3

# Cap on how many drainage nodes get a full risk computation per request
# for the granular, per-manhole view (node_risk_points). Prevents an
# unexpectedly huge BMC layer from making that endpoint slow.
DEFAULT_NODE_LIMIT = 500


# ---------------------------------------------------------------------
# Legacy helpers — kept as-is in case other modules (e.g. the Aeravat
# chat agent) import them for single-point lookups by lat/lon.
# ---------------------------------------------------------------------

def _latest_rain(db: Session, lat: float, lon: float):
    latest = db.query(RainfallObservation).order_by(desc(RainfallObservation.timestamp)).first()
    if not latest:
        return None
    candidates = db.query(RainfallObservation).filter(
        RainfallObservation.timestamp == latest.timestamp
    ).all()
    return min(candidates, key=lambda r: (r.latitude - lat) ** 2 + (r.longitude - lon) ** 2)


def _nearest_water(db: Session, lat: float, lon: float):
    rows = db.query(WaterObservation).order_by(desc(WaterObservation.timestamp)).limit(100).all()
    if not rows:
        return None
    return min(rows, key=lambda x: (x.latitude - lat) ** 2 + (x.longitude - lon) ** 2)


def _assets_near(db: Session, lat: float, lon: float, radius: float = .01):
    """Legacy static-DrainageAsset lookup. No longer used by all_cells()
    (see _nearest_node_dict below, which sources live graph data instead),
    kept for any other callers."""
    rows = db.query(DrainageAsset).filter(
        DrainageAsset.latitude.between(lat - radius, lat + radius),
        DrainageAsset.longitude.between(lon - radius, lon + radius),
    ).all()
    return [{"id": a.id, "name": a.name, "asset_type": a.asset_type, "latitude": a.latitude,
             "longitude": a.longitude, "capacity_lps": a.capacity_lps,
             "current_flow_lps": a.current_flow_lps} for a in rows]


def cell_status(db: Session, cell: SpatialCell) -> dict:
    """Legacy single-SpatialCell risk computation using the static
    DrainageAsset table. No longer used by all_cells() (see zone_status
    below, which sources drainage data from the live BMC graph instead),
    kept for any other callers."""
    rain = _latest_rain(db, cell.latitude, cell.longitude)
    water = _nearest_water(db, cell.latitude, cell.longitude)
    assets = _assets_near(db, cell.latitude, cell.longitude)
    ratio, drainage = asset_stress(assets)
    rain_i = (rain.rain_60m_mm if rain and rain.rain_60m_mm is not None else 0.0)
    features = build_features(
        rain_15m_mm=rain.rain_15m_mm if rain else None,
        rain_60m_mm=rain.rain_60m_mm if rain else None,
        rain_180m_mm=rain.rain_180m_mm if rain else None,
        elevation_m=cell.elevation_m,
        slope_pct=cell.slope_pct,
        distance_to_drain_m=None,
        drainage_capacity_ratio=ratio,
        tide_m=0.0,
        historical_flood_frequency=cell.historical_flood_frequency,
        impervious_fraction=cell.impervious_fraction,
    )
    ml = predict(features)
    risk = calculate_risk(model_probability=ml["probability"] if ml["model_status"] == "trained" else None,
                           rain_intensity=rain_i, drainage_ratio=ratio,
                           water_level_cm=water.level_cm if water else 0,
                           terrain_vulnerability=max(0.0, 1.0 - (cell.elevation_m or 0) / 20.0),
                           tide_m=0.0, historical_frequency=cell.historical_flood_frequency,
                           confidence=ml["confidence"])
    rain_15 = rain.rain_15m_mm if rain and rain.rain_15m_mm is not None else 0.0
    rainfall_trend_val = (rain_15 * 4.0) - rain_i
    return {
        "cell_id": cell.id, "latitude": cell.latitude, "longitude": cell.longitude,
        "ward_name": cell.ward_name, "score": risk.score, "level": risk.level,
        "drivers": risk.drivers, "method": risk.method,
        "model": ml, "rainfall": {"source": rain.source if rain else None,
                                    "rain_15m_mm": rain.rain_15m_mm if rain else None,
                                    "rain_60m_mm": rain.rain_60m_mm if rain else None,
                                    "rain_180m_mm": rain.rain_180m_mm if rain else None,
                                    "timestamp": rain.timestamp.isoformat() if rain else None,
                                    "observed": bool(rain and rain.is_observed)},
        "water_level_cm": water.level_cm if water else None,
        "drainage_utilization_pct": round(ratio * 100, 1), "drainage_assets": drainage,
        
       "nowcast": nowcast(current_score=risk.score, rain_intensity=rain_i, drainage_ratio=ratio, water_level_cm=(water.level_cm if water else 0), rainfall_trend=rainfall_trend_val, drainage_stress=ratio),
        "recommended_actions": recommendations(risk_level=risk.level, drainage_ratio=ratio,
                                                water_level_cm=water.level_cm if water else 0,
                                                latitude=cell.latitude, longitude=cell.longitude),
        "confidence": ml["confidence"],
    }


# ---------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------

def _nearest_from_list(items: list, lat: float, lon: float):
    """Nearest match among ORM objects (has .latitude/.longitude attrs)."""
    if not items:
        return None
    return min(items, key=lambda x: (x.latitude - lat) ** 2 + (x.longitude - lon) ** 2)


def _nearest_dict(items: list[dict], lat: float, lon: float) -> dict | None:
    """Nearest match among plain dicts (has ["latitude"]/["longitude"] keys)."""
    if not items:
        return None
    return min(items, key=lambda x: (x["latitude"] - lat) ** 2 + (x["longitude"] - lon) ** 2)


def _assets_from_edges(node: dict, edges_by_node: dict) -> list[dict]:
    """
    Builds an asset-shaped list from the live simulated drainage edges
    connected to a graph node, instead of the static seeded DrainageAsset
    table. capacity_lps/simulated_flow_lps already reflect current
    rainfall (computed in build_drainage_graph), so utilization here
    moves with the weather instead of being frozen at seed time.
    """
    edges = edges_by_node.get(node["id"], [])
    return [{
        "id": e["id"],
        "name": f"Drain {e['id']}",
        "asset_type": "storm_water_drain",
        "latitude": node["latitude"],
        "longitude": node["longitude"],
        "capacity_lps": e["capacity_lps"],
        "current_flow_lps": e["simulated_flow_lps"],
    } for e in edges]


def _graph_drainage_ratio(lat: float, lon: float, nodes: list[dict], edges_by_node: dict) -> tuple[float, list[dict]]:
    """
    Finds the live BMC drainage-graph node nearest to (lat, lon) and
    returns its current (rainfall-driven) utilization ratio plus an
    asset-shaped breakdown of its connected drain edges. Falls back to
    (0.0, []) if the graph has no nodes at all.
    """
    nearest_node = _nearest_dict(nodes, lat, lon)
    if not nearest_node:
        return 0.0, []
    assets = _assets_from_edges(nearest_node, edges_by_node)
    if assets:
        return asset_stress(assets)
    return nearest_node["utilization_pct"] / 100.0, []


# ---------------------------------------------------------------------
# Zone-level risk (default): ALWAYS one entry per known Mumbai locality
# (SpatialCell), so the Overview dashboard/map keeps showing every known
# area regardless of how real BMC drainage data happens to be
# distributed. Drainage utilization is sourced from the live graph
# (nearest node), not a static snapshot, so it still moves with rainfall.
# ---------------------------------------------------------------------

def zone_status(
    zone: SpatialCell,
    rain_candidates: list,
    water_rows: list,
    graph_nodes: list[dict],
    edges_by_node: dict,
) -> dict:
    lat, lon = zone.latitude, zone.longitude

    rain = _nearest_from_list(rain_candidates, lat, lon)
    water = _nearest_from_list(water_rows, lat, lon)
    ratio, drainage = _graph_drainage_ratio(lat, lon, graph_nodes, edges_by_node)

    rain_i = rain.rain_60m_mm if rain and rain.rain_60m_mm is not None else 0.0

    features = build_features(
        rain_15m_mm=rain.rain_15m_mm if rain else None,
        rain_60m_mm=rain.rain_60m_mm if rain else None,
        rain_180m_mm=rain.rain_180m_mm if rain else None,
        elevation_m=zone.elevation_m,
        slope_pct=zone.slope_pct,
        distance_to_drain_m=None,
        drainage_capacity_ratio=ratio,
        tide_m=0.0,
        historical_flood_frequency=zone.historical_flood_frequency,
        impervious_fraction=zone.impervious_fraction,
    )
    ml = predict(features)
    risk = calculate_risk(
        model_probability=ml["probability"] if ml["model_status"] == "trained" else None,
        rain_intensity=rain_i,
        drainage_ratio=ratio,
        water_level_cm=water.level_cm if water else 0,
        terrain_vulnerability=max(0.0, 1.0 - (zone.elevation_m or 0) / 20.0),
        tide_m=0.0,
        historical_frequency=zone.historical_flood_frequency,
        confidence=ml["confidence"],
    )
    rain_15 = rain.rain_15m_mm if rain and rain.rain_15m_mm is not None else 0.0
    rainfall_trend_val = (rain_15 * 4.0) - rain_i
    return {
        "cell_id": zone.id, "latitude": lat, "longitude": lon,
        "ward_name": zone.ward_name, "score": risk.score, "level": risk.level,
        "drivers": risk.drivers, "method": risk.method,
        "model": ml,
        "rainfall": {
            "source": rain.source if rain else None,
            "rain_15m_mm": rain.rain_15m_mm if rain else None,
            "rain_60m_mm": rain.rain_60m_mm if rain else None,
            "rain_180m_mm": rain.rain_180m_mm if rain else None,
            "timestamp": rain.timestamp.isoformat() if rain else None,
            "observed": bool(rain and rain.is_observed),
        },
        "water_level_cm": water.level_cm if water else None,
        "drainage_utilization_pct": round(ratio * 100, 1),
        "drainage_assets": drainage,
        "nowcast": nowcast(current_score=risk.score, rain_intensity=rain_i, drainage_ratio=ratio, water_level_cm=(water.level_cm if water else 0), rainfall_trend=rainfall_trend_val, drainage_stress=ratio),
        "recommended_actions": recommendations(
            risk_level=risk.level, drainage_ratio=ratio,
            water_level_cm=water.level_cm if water else 0,
            latitude=lat, longitude=lon,
        ),
        "confidence": ml["confidence"],
    }


async def all_cells(db: Session) -> list[dict]:
    """
    Zone-level risk view — ALWAYS returns one entry per known Mumbai
    locality (every row in SpatialCell), so the Overview dashboard/map
    and alerts keep showing every known area, not just wherever real BMC
    drainage nodes happen to be concentrated. Each zone's drainage
    utilization comes from the live rainfall-driven graph (nearest node),
    not the old static DrainageAsset snapshot.
    """
    graph = await build_drainage_graph(db)
    graph_nodes = graph["nodes"]
    edges = graph["edges"]

    edges_by_node: dict[str, list[dict]] = defaultdict(list)
    for e in edges:
        if e.get("from_node"):
            edges_by_node[e["from_node"]].append(e)
        if e.get("to_node"):
            edges_by_node[e["to_node"]].append(e)

    latest_rain = db.query(RainfallObservation).order_by(desc(RainfallObservation.timestamp)).first()
    rain_candidates = (
        db.query(RainfallObservation).filter(RainfallObservation.timestamp == latest_rain.timestamp).all()
        if latest_rain else []
    )
    water_rows = db.query(WaterObservation).order_by(desc(WaterObservation.timestamp)).limit(100).all()
    zones = db.query(SpatialCell).all()

    return [
        zone_status(z, rain_candidates, water_rows, graph_nodes, edges_by_node)
        for z in zones
    ]


# ---------------------------------------------------------------------
# Node-level risk (granular): one entry per real BMC manhole node.
# Use this for drainage-network visualization and street-level flood
# risk work — NOT for the Overview dashboard/map, since the number and
# geographic spread of real nodes varies with what BMC's GIS layer
# actually covers.
# ---------------------------------------------------------------------

def node_status(
    node: dict,
    rain_candidates: list,
    water_rows: list,
    terrain_cells: list,
    edges_by_node: dict,
) -> dict:
    lat, lon = node["latitude"], node["longitude"]

    rain = _nearest_from_list(rain_candidates, lat, lon)
    water = _nearest_from_list(water_rows, lat, lon)
    terrain = _nearest_from_list(terrain_cells, lat, lon)

    assets = _assets_from_edges(node, edges_by_node)
    if assets:
        ratio, drainage = asset_stress(assets)
    else:
        ratio, drainage = node["utilization_pct"] / 100.0, []

    rain_i = rain.rain_60m_mm if rain and rain.rain_60m_mm is not None else 0.0

    elevation_m = terrain.elevation_m if terrain and terrain.elevation_m is not None else DEFAULT_ELEVATION_M
    slope_pct = terrain.slope_pct if terrain and terrain.slope_pct is not None else DEFAULT_SLOPE_PCT
    impervious_fraction = (
        terrain.impervious_fraction if terrain and terrain.impervious_fraction is not None
        else DEFAULT_IMPERVIOUS_FRACTION
    )
    historical_flood_frequency = (
        terrain.historical_flood_frequency if terrain and terrain.historical_flood_frequency is not None
        else DEFAULT_HIST_FLOOD_FREQUENCY
    )
    ward_name = terrain.ward_name if terrain else None

    features = build_features(
        rain_15m_mm=rain.rain_15m_mm if rain else None,
        rain_60m_mm=rain.rain_60m_mm if rain else None,
        rain_180m_mm=rain.rain_180m_mm if rain else None,
        elevation_m=elevation_m,
        slope_pct=slope_pct,
        distance_to_drain_m=None,
        drainage_capacity_ratio=ratio,
        tide_m=0.0,
        historical_flood_frequency=historical_flood_frequency,
        impervious_fraction=impervious_fraction,
    )
    ml = predict(features)
    risk = calculate_risk(
        model_probability=ml["probability"] if ml["model_status"] == "trained" else None,
        rain_intensity=rain_i,
        drainage_ratio=ratio,
        water_level_cm=water.level_cm if water else 0,
        terrain_vulnerability=max(0.0, 1.0 - elevation_m / 20.0),
        tide_m=0.0,
        historical_frequency=historical_flood_frequency,
        confidence=ml["confidence"],
    )
    rain_15 = rain.rain_15m_mm if rain and rain.rain_15m_mm is not None else 0.0
    rainfall_trend_val = (rain_15 * 4.0) - rain_i
    return {
        "cell_id": node["id"], "latitude": lat, "longitude": lon,
        "ward_name": ward_name, "score": risk.score, "level": risk.level,
        "drivers": risk.drivers, "method": risk.method,
        "model": ml,
        "rainfall": {
            "source": rain.source if rain else None,
            "rain_15m_mm": rain.rain_15m_mm if rain else None,
            "rain_60m_mm": rain.rain_60m_mm if rain else None,
            "rain_180m_mm": rain.rain_180m_mm if rain else None,
            "timestamp": rain.timestamp.isoformat() if rain else None,
            "observed": bool(rain and rain.is_observed),
        },
        "water_level_cm": water.level_cm if water else None,
        "drainage_utilization_pct": round(ratio * 100, 1),
        "drainage_assets": drainage,
        "nowcast": nowcast(current_score=risk.score, rain_intensity=rain_i, drainage_ratio=ratio, water_level_cm=(water.level_cm if water else 0), rainfall_trend=rainfall_trend_val, drainage_stress=ratio),
        "recommended_actions": recommendations(
            risk_level=risk.level, drainage_ratio=ratio,
            water_level_cm=water.level_cm if water else 0,
            latitude=lat, longitude=lon,
        ),
        "confidence": ml["confidence"],
    }


async def node_risk_points(db: Session, limit: int = DEFAULT_NODE_LIMIT) -> list[dict]:
    """
    Risk points, one per real BMC drainage-graph node (manhole), so every
    flood-risk marker sits exactly where a real manhole is — and its
    drainage_ratio comes from that node's live, rainfall-driven
    utilization. Use for drainage-network views / street-level modeling,
    not the Overview dashboard.
    """
    graph = await build_drainage_graph(db)
    nodes = graph["nodes"][:limit]
    edges = graph["edges"]

    edges_by_node: dict[str, list[dict]] = defaultdict(list)
    for e in edges:
        if e.get("from_node"):
            edges_by_node[e["from_node"]].append(e)
        if e.get("to_node"):
            edges_by_node[e["to_node"]].append(e)

    latest_rain = db.query(RainfallObservation).order_by(desc(RainfallObservation.timestamp)).first()
    rain_candidates = (
        db.query(RainfallObservation).filter(RainfallObservation.timestamp == latest_rain.timestamp).all()
        if latest_rain else []
    )
    water_rows = db.query(WaterObservation).order_by(desc(WaterObservation.timestamp)).limit(100).all()
    terrain_cells = db.query(SpatialCell).all()

    return [
        node_status(n, rain_candidates, water_rows, terrain_cells, edges_by_node)
        for n in nodes
    ]