import numpy as np
from sklearn.ensemble import IsolationForest

def detect(values: list[float]) -> dict:
    if len(values) < 8:
        return {"is_anomaly": False, "score": 0.0, "reason": "Insufficient recent history"}
    x = np.asarray(values, dtype=float).reshape(-1, 1)
    model = IsolationForest(n_estimators=150, contamination="auto", random_state=42)
    model.fit(x[:-1])
    prediction = int(model.predict(x[-1:])[0])
    return {
        "is_anomaly": prediction == -1,
        "score": round(float(-model.score_samples(x[-1:])[0]), 4),
        "reason": "Observation differs materially from recent pattern" if prediction == -1 else "Within recent pattern",
    }
