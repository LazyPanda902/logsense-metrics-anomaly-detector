import os, sys
from datetime import datetime, timedelta

import streamlit as st
import pandas as pd
import numpy as np
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

st.set_page_config(page_title="LogSense Dashboard", layout="wide")
st.title("LogSense: Metrics Anomaly Detector")
st.caption("By Ali Bidhendi")

api_url = st.text_input("API URL", value="http://localhost:8000/detect")


def make_sample_metrics(n: int = 240, freq_seconds: int = 60, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = datetime.now() - timedelta(seconds=n * freq_seconds)

    ts = [(start + timedelta(seconds=i * freq_seconds)).isoformat(timespec="seconds") for i in range(n)]

    cpu = np.clip(rng.normal(30, 6, n), 0, 100)
    ram = np.clip(rng.normal(55, 7, n), 0, 100)
    disk = np.clip(rng.normal(20, 3, n), 0, 100)
    latency = np.clip(rng.normal(120, 15, n), 10, 2000)

    # Spikes (cause anomalies)
    spike_idx = rng.choice(np.arange(20, n - 20), size=max(3, n // 80), replace=False)
    for idx in spike_idx:
        cpu[idx] = np.clip(cpu[idx] + rng.uniform(40, 65), 0, 100)
        ram[idx] = np.clip(ram[idx] + rng.uniform(20, 35), 0, 100)
        latency[idx] = np.clip(latency[idx] + rng.uniform(400, 1200), 10, 2000)

    # Drift (gradual change)
    drift_start = int(n * 0.65)
    drift_end = int(n * 0.85)
    drift = np.linspace(0, 250, drift_end - drift_start)
    latency[drift_start:drift_end] = np.clip(latency[drift_start:drift_end] + drift, 10, 2000)

    return pd.DataFrame({
        "ts": ts,
        "cpu": np.round(cpu, 2),
        "ram": np.round(ram, 2),
        "disk": np.round(disk, 2),
        "latency_ms": np.round(latency, 2),
    })


if "df" not in st.session_state:
    st.session_state.df = None

tab1, tab2 = st.tabs(["Detect", "Run History"])

with tab1:
    top_left, top_right = st.columns([1, 1])

    with top_left:
        st.subheader("Quick Demo")
        demo_cols = st.columns(3)
        with demo_cols[0]:
            n_points = st.number_input("Points", min_value=60, max_value=2000, value=240, step=60)
        with demo_cols[1]:
            freq = st.selectbox("Interval (seconds)", [30, 60, 120, 300], index=1)
        with demo_cols[2]:
            seed = st.number_input("Seed", min_value=1, max_value=9999, value=42, step=1)

        if st.button("Generate sample data", type="primary"):
            st.session_state.df = make_sample_metrics(n=int(n_points), freq_seconds=int(freq), seed=int(seed))
            st.success("Sample data generated. Scroll down to detect anomalies.")

    with top_right:
        st.subheader("Upload CSV")
        st.write("Required columns: ts,cpu,ram,disk,latency_ms")
        file = st.file_uploader("Choose CSV", type=["csv"])
        if file:
            df_upload = pd.read_csv(file)
            required = {"ts", "cpu", "ram", "disk", "latency_ms"}
            missing = required - set(df_upload.columns)
            if missing:
                st.error(f"Missing columns: {sorted(list(missing))}")
                st.stop()
            st.session_state.df = df_upload.copy()
            st.success("CSV loaded. Scroll down to detect anomalies.")

    st.divider()

    df = st.session_state.df
    if df is None:
        st.info("Generate sample data above, or upload a CSV to begin.")
        st.stop()

    df = df.copy()
    df["ts"] = df["ts"].astype(str)
    df = df.sort_values("ts")

    left, right = st.columns([1.2, 1])

    with left:
        st.markdown("### Preview")
        st.dataframe(df.head(60), use_container_width=True)

        st.markdown("### Metric Charts")
        chart_df = df.set_index("ts")[["cpu", "ram", "disk", "latency_ms"]]
        st.line_chart(chart_df, use_container_width=True)

    with right:
        st.markdown("### Detection (saves to SQLite)")

        # NEW: sensitivity slider
        contamination = st.slider(
            "Sensitivity (contamination)",
            min_value=0.01,
            max_value=0.30,
            value=0.05,
            step=0.01,
            help="Higher = more anomalies flagged. Example: 0.05 with 240 points ~ 12 anomalies."
        )

        expected = int(round(len(df) * float(contamination)))
        st.caption(f"Expected anomalies (roughly): ~{expected} out of {len(df)} points")

        if st.button("Detect anomalies", type="primary"):
            payload = {
                "points": df.to_dict(orient="records"),
                "contamination": float(contamination),
            }

            try:
                r = requests.post(api_url, json=payload, timeout=60)
                r.raise_for_status()
            except Exception as e:
                st.error(f"Request failed: {e}")
                st.stop()

            data = r.json()

            st.success("Detection complete.")
            st.metric("Total points", data["total_points"])
            st.metric("Anomalies found", data["anomalies_found"])

            anomalies = pd.DataFrame(data["anomalies"])
            if len(anomalies) == 0:
                st.info("No anomalies found in this batch.")
            else:
                anomalies = anomalies.sort_values("score", ascending=False)
                st.dataframe(anomalies, use_container_width=True)

with tab2:
    st.subheader("Saved Runs (from logsense.db)")
    base = api_url.replace("/detect", "")
    runs_url = f"{base}/runs"

    try:
        runs_resp = requests.get(runs_url, timeout=10)
        runs_resp.raise_for_status()
        runs = runs_resp.json()["runs"]
    except Exception as e:
        st.error(f"Could not load runs: {e}")
        st.stop()

    if not runs:
        st.info("No saved runs yet. Go to Detect tab and run detection once.")
        st.stop()

    runs_df = pd.DataFrame(runs)
    st.dataframe(runs_df, use_container_width=True)

    run_id = st.number_input(
        "Enter run_id to view anomalies",
        min_value=1,
        value=int(runs_df.iloc[0]["id"])
    )

    anomalies_url = f"{base}/runs/{int(run_id)}/anomalies"

    try:
        a_resp = requests.get(anomalies_url, timeout=10)
        a_resp.raise_for_status()
        anomalies = a_resp.json()["anomalies"]
    except Exception as e:
        st.error(f"Could not load anomalies: {e}")
        st.stop()

    st.markdown(f"### Anomalies for run {int(run_id)}")
    st.dataframe(pd.DataFrame(anomalies), use_container_width=True)

