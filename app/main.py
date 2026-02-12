"""
LogSense API
Author: Ali Bidhendi

POST /detect
- Accepts a list of metric points
- Returns anomalies
"""

from fastapi import FastAPI
import pandas as pd

from app.schemas import IngestRequest, DetectResponse, Anomaly
from app.detector import detect_anomalies, explain_fields

app = FastAPI(title="LogSense API", version="0.1")

@app.get("/")
def home():
    return {"message": "LogSense running", "author": "Ali Bidhendi"}

@app.post("/detect", response_model=DetectResponse)
def detect(req: IngestRequest):
    rows = [p.model_dump() for p in req.points]
    df = pd.DataFrame(rows)

    out, _ = detect_anomalies(df, contamination=0.05)

    anomalies = []
    for _, r in out[out["anomaly"]].iterrows():
        fields = explain_fields(r)
        anomalies.append(Anomaly(
            ts=str(r["ts"]),
            score=float(r["score"]),
            fields=fields,
            note=f"Unusual behavior detected. Check: {', '.join(fields)}"
        ))

    return DetectResponse(
        total_points=len(out),
        anomalies_found=len(anomalies),
        anomalies=anomalies
    )
