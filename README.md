LogSense: Metrics Anomaly Detector
Author: Ali Bidhendi

Overview
LogSense detects unusual behavior in system metrics such as CPU, RAM, disk usage, and request latency.
It exposes a small FastAPI backend for anomaly detection and a Streamlit dashboard for uploading data and viewing results.

Why this project matters (internship-ready)
- Real-world monitoring problem: find anomalies before incidents
- Uses ML (Isolation Forest) + clean API design
- Includes a UI demo and an explainable “what looks wrong” output
- Easy to extend into a production-style monitoring pipeline

Features
- Upload a CSV of metrics
- Run anomaly detection using IsolationForest
- Returns:
  - anomaly score
  - timestamps flagged as anomalous
  - top suspicious fields (simple explanation)
- Streamlit dashboard to view results

Tech stack
- Python
- pandas, numpy
- scikit-learn (IsolationForest)
- FastAPI (API)
- Streamlit (UI)

Project structure
logsense/
  app/
    __init__.py
    schemas.py
    detector.py
    main.py
  ui/
    streamlit_app.py
  data/
    sample_metrics.csv

Input format (CSV)
Required columns:
- ts (timestamp string)
- cpu
- ram
- disk
- latency_ms

Example:
ts,cpu,ram,disk,latency_ms
2026-02-11T00:00:00,25,40,10,120

How to run
1) Install
cd logsense
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

2) Start API
python -m uvicorn app.main:app --reload

3) Start UI (new terminal, same venv)
python -m streamlit run ui/streamlit_app.py

API usage
POST /detect
Body:
{
  "points": [
    {"ts": "...", "cpu": 25, "ram": 40, "disk": 10, "latency_ms": 120}
  ]
}

Returns:
- total_points
- anomalies_found
- anomalies: list of {ts, score, fields, note}

Next upgrades
- Rolling window detection for streaming metrics
- Save history to SQLite
- Better explanations (SHAP)
- Alerting (email/Slack) + threshold rules
- Docker + GitHub Actions CI
