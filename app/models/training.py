"""
Historical flood-model training pipeline.

Expected training rows are produced from real observations/reconstructions:
one row = one spatial cell/time window, with label 1 for observed/reconstructed
flood and 0 for observed non-flood.

CSV columns must include FEATURES + label.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .flood_model import FEATURES, train


def load_csv(path: str | Path) -> tuple[list[dict[str, Any]], list[int]]:
    path = Path(path)
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    required = set(FEATURES) | {"label"}
    missing = required - set(rows[0].keys()) if rows else required
    if missing:
        raise ValueError(f"Missing training columns: {sorted(missing)}")

    X = []
    y = []
    for row in rows:
        X.append({name: float(row[name]) for name in FEATURES})
        y.append(int(row["label"]))
    return X, y


def train_from_csv(path: str | Path) -> dict:
    X, y = load_csv(path)
    return train(X, y)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    args = parser.parse_args()

    result = train_from_csv(args.csv_path)
    print(result)
