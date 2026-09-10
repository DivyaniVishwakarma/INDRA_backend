from dataclasses import dataclass

@dataclass(frozen=True)
class RiskResult:
    score: float
    level: str
    drivers: list[str]
    method: str


def _clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


def _level(score: float) -> str:
    if score >= 0.78: return "critical"
    if score >= 0.58: return "high"
    if score >= 0.36: return "moderate"
    return "low"


def calculate_risk(*, model_probability: float | None, rain_intensity: float,
                   drainage_ratio: float, water_level_cm: float,
                   terrain_vulnerability: float, tide_m: float,
                   historical_frequency: float, confidence: float) -> RiskResult:
    # ML probability is primary when a trained model is available. The
    # deterministic component remains an explainable safety fallback/check.
    physics = (
        0.32 * _clip(rain_intensity / 100.0)
        + 0.28 * _clip(drainage_ratio)
        + 0.16 * _clip(water_level_cm / 60.0)
        + 0.08 * _clip(terrain_vulnerability)
        + 0.08 * _clip(tide_m / 2.5)
        + 0.08 * _clip(historical_frequency)
    )
    if model_probability is None:
        score = physics
        method = "explainable_physics_baseline"
    else:
        score = 0.75 * _clip(model_probability) + 0.25 * physics
        method = "supervised_ml_plus_physics_features"

    drivers: list[str] = []
    if rain_intensity >= 60: drivers.append(f"High rainfall intensity ({rain_intensity:.0f} mm/hr)")
    if drainage_ratio >= 0.85: drivers.append(f"Drainage capacity stress ({drainage_ratio * 100:.0f}%)")
    if water_level_cm >= 35: drivers.append(f"Elevated water level ({water_level_cm:.0f} cm)")
    if terrain_vulnerability >= 0.7: drivers.append("Low-lying / terrain vulnerability")
    if tide_m >= 1.5: drivers.append(f"Elevated tide ({tide_m:.1f} m)")
    if historical_frequency >= 0.7: drivers.append("Frequent historical flood exposure")
    if not drivers: drivers.append("No single dominant stressor")

    return RiskResult(round(_clip(score) * 100, 1), _level(score), drivers, method)
