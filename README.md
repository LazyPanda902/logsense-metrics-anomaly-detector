# LogSense: Metrics Anomaly Detector

**Author:** Ali Bidhendi

LogSense detects unusual behavior in time-series system metrics (CPU, RAM, disk usage, request latency).  
It includes a **FastAPI backend** for anomaly detection and a **Streamlit dashboard** to upload data, visualize metrics, run detection, and review saved runs.

---

## Why this project matters (internship-ready)
- Solves a real monitoring problem: detect anomalies before incidents.
- Combines **ML (IsolationForest)** with clean **API design (FastAPI)**.
- Includes a usable **UI demo (Streamlit)** with charts + run history.
- Produces an “explainable” output (which fields look suspicious).

---

## Features
- Upload a CSV of metrics (`ts,cpu,ram,disk,latency_ms`)
- Generate sample metric data (with **seed** control + randomize button)
- Run anomaly detection using **IsolationForest**
- Returns:
  - anomaly score per row
  - timestamps flagged as anomalous
  - suspicious fields + short note (“what looks wrong”)
- **SQLite persistence**
  - saves every detection run
  - browse prior runs in a **Run History** tab

---

## Tech stack
- Python
- pandas, numpy
- scikit-learn (IsolationForest)
- FastAPI (API)
- Streamlit (UI)
- SQLite (run history)

---

## Project structure
logsense/
app/
init.py
main.py
schemas.py
detector.py
db.py
ui/
streamlit_app.py
data/
sample_metrics.csv
logsense.db # created automatically when you run detections
---

## Input format (CSV)
Required columns:
- `ts` (timestamp string)
- `cpu`
- `ram`
- `disk`
- `latency_ms`

Example:
```csv
ts,cpu,ram,disk,latency_ms
2026-02-11T00:00:00,25,40,10,120
How to run locally
1) Setup
cd logsense
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
2) Start the API (FastAPI)
python -m uvicorn app.main:app --reload
API will run at:

http://127.0.0.1:8000

3) Start the UI (Streamlit) in a new terminal (same venv)
python -m streamlit run ui/streamlit_app.py
UI will run at:

http://localhost:8501

API endpoints
POST /detect
Runs anomaly detection on the provided points and saves the run to SQLite.

Body

{
  "points": [
    {"ts":"2026-02-11T00:00:00","cpu":25,"ram":40,"disk":10,"latency_ms":120}
  ]
}
Returns

run_id

total_points

anomalies_found

anomalies: list of {ts, score, fields, note}

GET /runs
Returns saved runs (id, timestamp, total_points, anomalies_found).

GET /runs/{run_id}
Returns the anomalies for a specific saved run.

Troubleshooting

UI shows connection refused: make sure the FastAPI server is running on http://localhost:8000

Wrong API URL in UI: check the “API URL” field at the top of the Streamlit page

If you changed ports, update the UI field accordingly.
