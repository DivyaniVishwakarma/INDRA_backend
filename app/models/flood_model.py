"""
Hybrid physics + ML flood-risk model.

The ML component is intentionally separated from the deterministic physical
features. Train it on labelled historical observations before calling the
model "trained". Until then, the API reports model_status="untrained".
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence
import joblib
import numpy as np

FEATURES = [
    "rain_15m_mm",
    "rain_60m_mm",
    "rain_180m_mm",
    "rain_intensity_mm_h",
    "elevation_m",
    "slope_pct",
    "distance_to_drain_m",
    "drainage_capacity_ratio",
    "tide_m",
    "historical_flood_frequency",
    "impervious_fraction",
]

MODEL_PATH = Path(__file__).resolve().parents[3] / "data" / "models" / "flood_risk.joblib"


def physics_score(x: dict) -> float:
    """
    Explainable baseline. It is not a trained ML prediction.
    """
    rain = min(1.0, float(x.get("rain_60m_mm", 0)) / 100.0)
    short = min(1.0, float(x.get("rain_15m_mm", 0)) / 40.0)
    drain = min(1.0, max(0.0, float(x.get("drainage_capacity_ratio", 0))))
    tide = min(1.0, max(0.0, float(x.get("tide_m", 0)) / 2.5))
    impervious = min(1.0, max(0.0, float(x.get("impervious_fraction", 0))))
    historical = min(1.0, max(0.0, float(x.get("historical_flood_frequency", 0))))

    # Rain + drainage mismatch is dominant, matching the project's SIH framing.
    score = (
        0.30 * rain
        + 0.15 * short
        + 0.25 * drain
        + 0.10 * tide
        + 0.10 * impervious
        + 0.10 * historical
    )
    return float(np.clip(score, 0, 1))


def load_model():
    if MODEL_PATH.exists():
        return joblib.load(MODEL_PATH)
    return None


def predict(features: dict) -> dict:
    model = load_model()

    vector = np.array([[float(features.get(k, 0.0)) for k in FEATURES]], dtype=float)

    if model is None:
        score = physics_score(features)
        return {
            "probability": round(score, 4),
            "model_status": "untrained",
            "method": "physics_baseline",
            "confidence": 55.0,
        }

    probability = float(model.predict_proba(vector)[0, 1])
    confidence = float(max(model.predict_proba(vector)[0]) * 100)
    return {
        "probability": round(probability, 4),
        "model_status": "trained",
        "method": "supervised_ml_plus_physics_features",
        "confidence": round(confidence, 1),
    }


def train(X: Sequence[dict], y: Sequence[int]) -> dict:
    """
    Train a RandomForest classifier on labelled historical cells/events.

    Labels must come from actual observed/reconstructed flood presence,
    not synthetic random labels.
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score, f1_score

    matrix = np.array([[float(row.get(k, 0.0)) for k in FEATURES] for row in X])
    labels = np.array(y, dtype=int)

    if len(set(labels.tolist())) < 2:
        raise ValueError("Training data must contain both flood and non-flood labels.")

    X_train, X_test, y_train, y_test = train_test_split(
        matrix, labels, test_size=0.2, random_state=42, stratify=labels
    )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=18,
        min_samples_leaf=3,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    p = model.predict_proba(X_test)[:, 1]
    pred = (p >= 0.5).astype(int)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    return {
        "saved_to": str(MODEL_PATH),
        "samples": int(len(labels)),
        "roc_auc": round(float(roc_auc_score(y_test, p)), 4),
        "f1": round(float(f1_score(y_test, pred)), 4),
        "features": FEATURES,
    }
