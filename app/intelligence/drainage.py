def utilization(flow: float | None, capacity: float | None) -> float:
    if not capacity or capacity <= 0: return 0.0
    return max(0.0, min(2.0, float(flow or 0) / float(capacity)))


def asset_stress(assets: list[dict]) -> tuple[float, list[dict]]:
    details, vals = [], []
    for a in assets:
        ratio = utilization(a.get("current_flow_lps"), a.get("capacity_lps"))
        vals.append(ratio)
        details.append({
            "asset_id": a.get("id"), "asset_name": a.get("name"),
            "asset_type": a.get("asset_type"), "latitude": a.get("latitude"),
            "longitude": a.get("longitude"), "utilization_pct": round(ratio * 100, 1),
            "status": "critical" if ratio >= 1 else "high" if ratio >= .85 else "loaded" if ratio >= .65 else "normal",
        })
    return (max(vals) if vals else 0.0), details


def bottlenecks(assets: list[dict]) -> list[dict]:
    _, details = asset_stress(assets)
    return sorted([x for x in details if x["utilization_pct"] >= 85], key=lambda x: -x["utilization_pct"])