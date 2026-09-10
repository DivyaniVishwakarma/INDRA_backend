def recommendations(*, risk_level: str, drainage_ratio: float, water_level_cm: float,
                     latitude: float | None = None, longitude: float | None = None) -> list[dict]:
    actions = []
    if drainage_ratio >= 1.0:
        actions.append({"type": "field_inspection", "priority": 1,
                        "description": "Inspect overloaded drainage assets and verify blockage / pump status."})
    elif drainage_ratio >= .85:
        actions.append({"type": "drainage_clearance", "priority": 2,
                        "description": "Prioritize inspection and clearance around high-load drainage assets."})
    if water_level_cm >= 35:
        actions.append({"type": "field_verification", "priority": 2,
                        "description": "Verify rising water conditions on site and update the incident state."})
    if risk_level in {"critical", "high"}:
        actions.append({"type": "traffic_control", "priority": 3,
                        "description": "Review exposed roads and activate appropriate traffic-control procedures."})
    return actions
