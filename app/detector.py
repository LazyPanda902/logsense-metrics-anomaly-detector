"""
LogSense Anomaly Detector
Author: Ali Bidhendi

Idea:
- Use IsolationForest to detect unusual metric patterns
- Return anomaly score + which fields are most suspicious

Notes:
- MVP uses a simple model trained on the incoming batch
- Upgrade later: rolling window + persistent model + seasonality handling
"""

from typing import List, Dict, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

FEATURES = ["cpu", "ram", "disk", "latency_ms"]

def detect_anomalies(df: pd.DataFrame, contamination: float = 0.05) -> Tuple[pd.DataFrame, IsolationForest]:
    """
    Returns a dataframe with:
    - anomaly (bool)
    - score (float): higher = more anomalous (we invert decision_function)
    """
    X = df[FEATURES].astype(float).values

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42
    )
    model.fit(X)

    # decision_function: higher = more normal, lower = more abnormal
    raw = model.decision_function(X)
    score = (-raw)  # invert so higher = more anomalous

    pred = model.predict(X)  # -1 anomaly, 1 normal
    df = df.copy()
    df["score"] = score
    df["anomaly"] = (pred == -1)
    return df, model

def explain_fields(row: pd.Series) -> List[str]:
    """
    Simple explanation: pick largest normalized fields.
    This is not SHAP, just a quick MVP explanation.
    """
    vals = np.array([row[f] for f in FEATURES], dtype=float)
    norm = (vals - vals.mean()) / (vals.std() + 1e-9)
    idx = np.argsort(-np.abs(norm))[:2]
    return [FEATURES[i] for i in idx]
