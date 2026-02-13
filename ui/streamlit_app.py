import os
import random
from datetime import datetime

import pandas as pd
import requests
import streamlit as st


# -----------------------------
# Ali Bidhendi - LogSense UI
# -----------------------------


REQUIRED_COLS = ["ts", "cpu", "ram", "disk", "latency_ms"]


def normalize_base_url(api_url: str) -> str:
    """
    Accepts either:
      - http://localhost:8000
      - http://localhost:8000/
      - http://localhost:8000/detect
      - http://localhost:8000/detect/
    and returns:
      - http://localhost:8000
    """
    u = (api_url or "").strip()
    if not u:
        return "http://localhost:8000"

    u = u.rstrip("/")

    # If user pasted /detect, strip it to get the API root
    if u.endswith("/detect"):
        u = u[: -len("/detect")]

    return u.rstrip("/")


def make_sample_data(points: int, interval_s: int, seed: int) -> pd.DataFrame:
    """
    Simple synthetic metrics generator (stable, predictable).
    We inject a few spikes so IsolationForest has something to find.
    """
    rng = random.Random(seed)
    start = datetime.now()

    rows = []
    for i in range(points):
        ts = (start.replace(microsecond=0) + pd.Timedelta(seconds=i * interval_s)).isoformat()

        # Baseline ranges
        cpu = 15 + rng.random() * 25          # ~15-40
        ram = 45 + rng.random() * 25          # ~45-70
        disk = 10 + rng.random() * 15         # ~10-25
        latency = 80 + rng.random() * 60      # ~80-140

        # Inject some anomalies (spikes)
        if rng.random() < 0.04:
            latency *= (2.5 + rng.random() * 2.0)  # big spike
        if rng.random() < 0.03:
            disk *= (2.0 + rng.random() * 2.0)

        rows.append(
            {
                "ts": ts,
                "cpu": round(cpu, 2),
                "ram": round(ram, 2),
                "disk": round(disk, 2),
                "latency_ms": round(latency, 2),
            }
        )

    return pd.DataFrame(rows)


# -----------------------------
# Streamlit App
# -----------------------------
st.set_page_config(page_title="LogSense Dashboard", layout="wide")

st.title("LogSense: Metrics Anomaly Detector")
st.caption("By Ali Bidhendi")

# Let user paste either root or /detect; we normalize it
api_url_input = st.text_input("API URL", value="http://localhost:8000/detect")
base_url = normalize_base_url(api_url_input)
detect_url = f"{base_url}/detect"

tab1, tab2 = st.tabs(["Detect", "Run History"])


# ============================================================
# TAB 1: Detect
# ============================================================
with tab1:
    st.subheader("Quick Demo")

    left, right = st.columns([1.2, 1.0], gap="large")

    # --- LEFT SIDE (demo generator) ---
    with left:
        c1, c2, c3 = st.columns([1.0, 1.0, 1.1], gap="medium")

        with c1:
            points = st.number_input("Points", min_value=50, max_value=5000, value=240, step=10)

        with c2:
            interval_s = st.selectbox("Interval (seconds)", [1, 5, 10, 30, 60, 120], index=4)

        with c3:
            if "seed" not in st.session_state:
                st.session_state.seed = 42

            seed = st.number_input("Seed", min_value=0, max_value=999999, value=int(st.session_state.seed), step=1)
            st.session_state.seed = int(seed)

            # Buttons stacked UNDER the seed
            if st.button("Randomize seed 🎲", use_container_width=True):
                st.session_state.seed = random.randint(0, 999999)
                st.rerun()

            gen_clicked = st.button("Generate sample data", type="primary", use_container_width=True)

        # Store df in session state
        if "df" not in st.session_state:
            st.session_state.df = None

        # Upload CSV (still supported)
        st.markdown("### Upload CSV")
        uploaded = st.file_uploader(
            "Choose CSV",
            type=["csv"],
            help="Required columns: ts,cpu,ram,disk,latency_ms",
        )

        if gen_clicked:
            st.session_state.df = make_sample_data(int(points), int(interval_s), int(st.session_state.seed))
            st.success(f"Sample data generated (seed={st.session_state.seed}). Scroll down to detect anomalies.")

        if uploaded is not None:
            try:
                df_up = pd.read_csv(uploaded)
                st.session_state.df = df_up
                st.success("CSV loaded. Scroll down to detect anomalies.")
            except Exception as e:
                st.error(f"Could not read CSV: {e}")

        st.divider()

        df = st.session_state.df
        if df is None:
            st.info("Generate sample data above, or upload a CSV to begin.")
            st.stop()

        missing = [c for c in REQUIRED_COLS if c not in df.columns]
        if missing:
            st.error(f"CSV is missing required columns: {', '.join(missing)}")
            st.stop()

        st.markdown("### Preview")
        st.dataframe(df.head(60), use_container_width=True)

        st.markdown("### Metric Charts")
        try:
            chart_df = df.set_index("ts")[["cpu", "ram", "disk", "latency_ms"]]
            st.line_chart(chart_df, use_container_width=True)
        except Exception as e:
            st.warning(f"Could not render charts: {e}")

    # --- RIGHT SIDE (detection + settings) ---
    with right:
        st.subheader("Detection (saves to SQLite)")
        contamination = st.slider(
            "Sensitivity (contamination)",
            min_value=0.01,
            max_value=0.20,
            value=0.03,
            step=0.01,
            help="Higher = more anomalies flagged",
        )
        st.caption(f"Detect URL: {detect_url}")

        if st.button("Detect anomalies", type="primary", use_container_width=True):
            payload = {"points": df.to_dict(orient="records"), "contamination": float(contamination)}

            try:
                r = requests.post(detect_url, json=payload, timeout=60)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                st.error(f"Request failed: {e}")
                st.stop()

            st.success("Detection complete.")
            st.metric("Total points", data.get("total_points", len(df)))
            st.metric("Anomalies found", data.get("anomalies_found", 0))

            anomalies = pd.DataFrame(data.get("anomalies", []))
            if anomalies.empty:
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

    # Sort newest first if fields exist
    if "created_at" in runs_df.columns:
        runs_df = runs_df.sort_values("created_at", ascending=False)
    elif "id" in runs_df.columns:
        runs_df = runs_df.sort_values("id", ascending=False)

    st.dataframe(runs_df, use_container_width=True)

    st.markdown("### View anomalies for a saved run")
    default_id = int(runs_df.iloc[0]["id"]) if "id" in runs_df.columns else 1
    run_id = st.number_input("Enter run_id to view anomalies", min_value=1, value=default_id, step=1)

    try:
        ar = requests.get(anomalies_url_tpl.format(run_id=int(run_id)), timeout=15)
        ar.raise_for_status()
        anomalies = ar.json()
    except Exception as e:
        st.error(f"Failed to load run {run_id}: {e}")
        st.stop()

    st.markdown(f"### Anomalies for run {int(run_id)}")
    a_df = pd.DataFrame(anomalies)
    if a_df.empty:
        st.info("No anomalies stored for this run.")
    else:
        if "score" in a_df.columns:
            a_df = a_df.sort_values("score", ascending=False)
        st.dataframe(a_df, use_container_width=True)

