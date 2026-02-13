# ui/streamlit_app.py
"""
LogSense: Metrics Anomaly Detector (Streamlit UI)
By Ali Bidhendi

UI features:
- Quick Demo (generate synthetic metrics with a seed)
- Upload CSV
- Detect anomalies via FastAPI backend (/detect)
- Save runs to SQLite (backend)
- Run History tab (list runs + view anomalies for a run)

Run:
  python3 -m streamlit run ui/streamlit_app.py
Backend (in another terminal):
  python3 -m uvicorn app.main:app --reload
"""

from __future__ import annotations

import os
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import streamlit as st


# ----------------------------
# Page config + tiny helpers
# ----------------------------
st.set_page_config(page_title="LogSense Dashboard", layout="wide")

def _init_state() -> None:
    if "seed" not in st.session_state:
        st.session_state.seed = 42
    if "df" not in st.session_state:
        st.session_state.df = None


def make_sample_metrics(n: int, freq_seconds: int, seed: int) -> pd.DataFrame:
    """
    Simple synthetic metrics generator.
    Produces columns: ts,cpu,ram,disk,latency_ms
    """
    rng = np.random.default_rng(seed)

    start = datetime.utcnow()
    ts = [start + pd.Timedelta(seconds=i * freq_seconds) for i in range(n)]
    ts = [t.isoformat(timespec="seconds") for t in ts]

    # Baseline signals
    cpu = np.clip(rng.normal(loc=28, scale=6, size=n), 1, 95)
    ram = np.clip(rng.normal(loc=58, scale=5, size=n), 10, 95)
    disk = np.clip(rng.normal(loc=18, scale=4, size=n), 1, 95)
    latency = np.clip(rng.normal(loc=110, scale=12, size=n), 20, 1500)

    # Inject a few spikes (varies with seed)
    k = max(3, int(n * 0.02))
    idx = rng.choice(np.arange(n), size=k, replace=False)

    cpu[idx] = np.clip(cpu[idx] + rng.normal(35, 10, size=k), 1, 99)
    disk[idx] = np.clip(disk[idx] + rng.normal(30, 10, size=k), 1, 99)
    latency[idx] = np.clip(latency[idx] + rng.normal(500, 200, size=k), 20, 2000)

    df = pd.DataFrame(
        {
            "ts": ts,
            "cpu": np.round(cpu, 2),
            "ram": np.round(ram, 2),
            "disk": np.round(disk, 2),
            "latency_ms": np.round(latency, 2),
        }
    )
    return df


# ----------------------------
# App UI
# ----------------------------
_init_state()

st.title("LogSense: Metrics Anomaly Detector")
st.caption("By Ali Bidhendi")

api_url = st.text_input("API URL", value="http://localhost:8000/detect")
base_url = api_url.rsplit("/", 1)[0]  # e.g. http://localhost:8000

tab1, tab2 = st.tabs(["Detect", "Run History"])


# ============================================================
# TAB 1: Detect
# ============================================================
with tab1:
    top_left, top_right = st.columns([1, 1])

    # ----------------------------
    # LEFT TOP: Quick Demo
    # ----------------------------
    with top_left:
        st.subheader("Quick Demo")

        demo_cols = st.columns(3)

        with demo_cols[0]:
            n_points = st.number_input(
                "Points",
                min_value=60,
                max_value=5000,
                value=240,
                step=60,
            )

        with demo_cols[1]:
            freq = st.selectbox("Interval (seconds)", [30, 60, 120, 300], index=1)

        # ✅ Seed + Randomize + Generate stacked in the SAME column
        with demo_cols[2]:
            seed = st.number_input(
                "Seed",
                min_value=1,
                max_value=9999,
                value=int(st.session_state.seed),
                step=1,
            )
            st.session_state.seed = int(seed)

            if st.button("Randomize seed 🎲", use_container_width=True):
                st.session_state.seed = int(np.random.default_rng().integers(1, 10000))
                st.toast(f"Seed set to {st.session_state.seed}", icon="🎲")
                st.rerun()

            if st.button("Generate sample data", type="primary", use_container_width=True):
                st.session_state.df = make_sample_metrics(
                    n=int(n_points),
                    freq_seconds=int(freq),
                    seed=int(st.session_state.seed),
                )
                st.success(
                    f"Sample data generated (seed={st.session_state.seed}). "
                    f"Scroll down to detect anomalies."
                )

    # ----------------------------
    # RIGHT TOP: Upload CSV
    # ----------------------------
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

    # ----------------------------
    # Need a dataset
    # ----------------------------
    df = st.session_state.df
    if df is None:
        st.info("Generate sample data above, or upload a CSV to begin.")
        st.stop()

    df = df.copy()
    df["ts"] = df["ts"].astype(str)
    df = df.sort_values("ts")

    left, right = st.columns([1.2, 1])

    # ----------------------------
    # LEFT: Preview + charts
    # ----------------------------
    with left:
        st.markdown("### Preview")
        st.dataframe(df.head(60), use_container_width=True)

        st.markdown("### Metric Charts")
        chart_df = df.set_index("ts")[["cpu", "ram", "disk", "latency_ms"]]
        st.line_chart(chart_df, use_container_width=True)

    # ----------------------------
    # RIGHT: Detection
    # ----------------------------
    with right:
        st.markdown("### Detection (saves to SQLite)")

        contamination = st.slider(
            "Sensitivity (contamination)",
            min_value=0.01,
            max_value=0.30,
            value=0.05,
            step=0.01,
            help="Higher = more anomalies flagged. Example: 0.05 with 240 points ~ 12 anomalies.",
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
            st.metric("Total points", data.get("total_points", len(df)))
            st.metric("Anomalies found", data.get("anomalies_found", 0))

            anomalies = pd.DataFrame(data.get("anomalies", []))
            if len(anomalies) == 0:
                st.info("No anomalies found in this batch.")
            else:
                if "score" in anomalies.columns:
                    anomalies = anomalies.sort_values("score", ascending=False)
                st.markdown("#### Anomalies (sorted by score)")
                st.dataframe(anomalies, use_container_width=True)


# ============================================================
# TAB 2: Run History
# ============================================================
with tab2:
    st.subheader("Saved Runs (from logsense.db)")

    runs_url = f"{base_url}/runs"
    anomalies_url_tpl = f"{base_url}/runs/{{run_id}}/anomalies"

    try:
        rr = requests.get(runs_url, timeout=15)
        rr.raise_for_status()
        runs = rr.json()
    except Exception as e:
        st.error(f"Could not load run history from backend: {e}")
        st.stop()

    if not runs:
        st.info("No saved runs yet. Go to Detect tab and run detection once.")
        st.stop()

    runs_df = pd.DataFrame(runs)
    # Nice ordering if fields exist
    for col in ["created_at", "id"]:
        if col in runs_df.columns:
            runs_df = runs_df.sort_values(col, ascending=False)

    st.dataframe(runs_df, use_container_width=True)

    st.markdown("### View anomalies for a saved run")
    default_id = int(runs_df.iloc[0]["id"]) if "id" in runs_df.columns else 1
    run_id = st.number_input("Enter run_id to view anomalies", min_value=1, value=default_id, step=1)

    try:
        ar = requests.get(anomalies_url_tpl.format(run_id=int(run_id)), timeout=15)
        ar.raise_for_status()
        anomalies = ar.json()
    except Exception as e:
        st.error(f"Could not load anomalies for run {run_id}: {e}")
        st.stop()

    st.markdown(f"### Anomalies for run {int(run_id)}")
    if not anomalies:
        st.info("No anomalies stored for this run.")
    else:
        a_df = pd.DataFrame(anomalies)
        if "score" in a_df.columns:
            a_df = a_df.sort_values("score", ascending=False)
        st.dataframe(a_df, use_container_width=True)

