from fastapi import FastAPI
import pandas as pd
from datetime import datetime

from app.schemas import IngestRequest, DetectResponse, Anomaly
from app.detector import detect_anomalies, explain_fields
from app.db import init_db, save_run, save_anomalies, list_runs, get_anomalies_for_run

app = FastAPI(title="LogSense API", version="0.3", description="By Ali Bidhendi")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def home():
    return {"message": "LogSense running", "author": "Ali Bidhendi"}


@app.post("/detect", response_model=DetectResponse)
def detect(req: IngestRequest):
    # Build DF from request
    rows = [p.model_dump() for p in req.points]
    df = pd.DataFrame(rows)

    # IMPORTANT: use contamination from the request
    # This controls sensitivity and prevents "always 12" on 240 points.
    out, _ = detect_anomalies(df, contamination=float(req.contamination))

    anomalies = []
    for _, r in out[out["anomaly"]].iterrows():
        fields = explain_fields(r)
        anomalies.append({
            "ts": str(r["ts"]),
            "score": float(r["score"]),
            "fields": fields,
            "note": f"Unusual behavior detected. Check: {', '.join(fields)}"
        })

    created_at = datetime.now().isoformat(timespec="seconds")
    run_id = save_run(created_at, total_points=len(out), anomalies_found=len(anomalies))
    if anomalies:
        save_anomalies(run_id, anomalies)

    return DetectResponse(
        total_points=len(out),
        anomalies_found=len(anomalies),
        anomalies=[Anomaly(**a) for a in anomalies]
    )


@app.get("/runs")
def runs(limit: int = 25):
    rows = list_runs(limit=limit)
    return {
        "runs": [
            {"id": r[0], "created_at": r[1], "total_points": r[2], "anomalies_found": r[3]}
            for r in rows
        ]
    }


@app.get("/runs/{run_id}/anomalies")
def run_anomalies(run_id: int):
    rows = get_anomalies_for_run(run_id)
    return {
        "run_id": run_id,
        "anomalies": [
            {"ts": r[0], "score": r[1], "fields": r[2].split(","), "note": r[3]}
            for r in rows
        ]
    }


