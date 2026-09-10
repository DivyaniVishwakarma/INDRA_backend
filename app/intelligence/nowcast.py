def _level(score: float) -> str:
    if score >= 78: return "critical"
    if score >= 58: return "high"
    if score >= 36: return "moderate"
    return "low"


def nowcast(*, current_score: float, rain_intensity: float = 0.0, drainage_ratio: float = 0.0,
            water_level_cm: float = 0.0, rainfall_trend: float = 0.0, drainage_stress: float = 0.0,
            horizon_minutes: tuple[int, ...] = (30, 60, 120, 180)) -> dict:
    # This is a short-horizon stress projection, not a claim of a trained
    # temporal model. A future temporal ML model can replace this function.
    trend = max(-10.0, min(20.0, rainfall_trend * 0.18 + drainage_stress * 8.0))
    out = {}
    for minutes in horizon_minutes:
        factor = minutes / 60.0
        score = max(0.0, min(100.0, current_score + trend * factor))
        # Same escalation/de-escalation trend driving the score is applied
        # to each underlying driver (rainfall, drainage, water level), so
        # the Risk Drivers panel actually moves as the horizon changes
        # instead of freezing at the current (T+0) reading for every tab.
        scale = max(0.0, 1.0 + (trend * factor) / 100.0)
        out[f"{minutes}_min"] = {
            "score": round(score, 1),
            "level": _level(score),
            "drivers": {
                "rain_intensity": round(max(0.0, rain_intensity * scale), 1),
                "drainage_ratio": round(max(0.0, drainage_ratio * scale), 3),
                "water_level_cm": round(max(0.0, water_level_cm * scale), 1),
            },
        }
    return out