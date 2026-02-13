import os
from datetime import datetime

import numpy as np
import pandas as pd
import requests
import streamlit as st


# ---------------------------
# Helpers
# ---------------------------
def make_sample_metrics(n: int, freq_seconds: int, seed: int) -> pd.DataFrame:
    """
    Create a toy metrics dataset with occasional spikes (anomalies).
    Columns: ts,cpu,ram,disk,latency_ms
    """
    rng = np.random.default_rng(seed)

    start = datetime.utcnow().replace(microsecond=0)
    ts = [start + pd.Timedelta(seconds=i * freq_seconds) for i in range(n)]

    cpu = rng.normal(25, 8, size=n).clip(0, 100)
    ram = rng.normal(55, 6, size=n).clip(0, 100)
    disk = rng.normal(20, 3, size=n).clip(0, 100)
    latency = rng.normal(120, 15, size=n).clip(1, None)

    # Inject a few spikes
    spike_count = max(3, n // 60)
    spike_idx = rng.choice(np.arange(n), size=spike_count, replace=False)
    latency[spike_idx] *= rng.uniform(4.0, 9.0, size=spike_count)
    disk[spike_idx] *= rng.uniform(2.0, 4.0, size=spike_count)

    df = pd.DataFrame(
        {
            "ts": pd.to_datetime(ts),
            "cpu": cpu.round(2),
            "ram": ram.round(2),
            "disk": disk.round(2),
            "latency_ms": latency.round(2),
        }
    )
    return df


def ensure_ts_str(df: pd.DataFrame) -> pd.DataFrame:
    df2 = df.copy()
    # Streamlit sometimes keeps ts as Timestamp; API can accept string.
    df2["ts"] = pd.to_datetime(df2["ts"]).dt.strftime("%Y-%m-%dT%H:%M:%S")
    return df2


# ---------------------------
# Streamlit app
# ---------------------------
st.set_page_config(page_title="LogSense", layout="wide")

st.title("LogSense: Metrics Anomaly Detector")
st.caption("By Ali Bidhendi")

default_api = os.environ.get("LOGSENSE_API_URL", "http://localhost:8000/detect")
api_url = st.text_input("API URL", value=default_api)

# Session state init
if "seed" not in st.session_state:
    st.session_state.seed = 42
if "df" not in st.session_state:
    st.session_state.df = None

tab_detect, tab_history = st.tabs(["Detect", "Run History"])

# ---------------------------
# Detect tab
# ---------------------------
with tab_detect:
    cols = st.columns(2, gap="large")
    top_left, top_right = cols[0], cols[1]

    with top_left:
        st.subheader("Quick Demo")

        # 3-column controls: Points | Interval | Seed (+ actions)
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

        with demo_cols[2]:
            seed = st.number_input(
                "Seed",
                min_value=0,
                max_value=10_000_000,
                value=int(st.session_state.seed),
                step=1,
            )
            st.session_state.seed = int(seed)

            # Put the randomizer + generate buttons UNDER the seed field (stacked).
            if st.button("Randomize seed 🎲"):
                st.session_state.seed = int(np.random.default_rng().integers(0, 10_000_000))
                st.rerun()

            if st.button("Generate sample data", type="primary"):
                st.session_state.df = make_sample_metrics(
                    n=int(n_points),
                    freq_seconds=int(freq),
                    seed=int(st.session_state.seed),
                )
                st.success(
                    f"Sample data generated (seed={st.session_state.seed}). Scroll down to detect anomalies."
                )

        df = st.session_state.df

    with top_right:
        st.subheader("Upload CSV")
        st.caption("Required columns: ts,cpu,ram,disk,latency_ms")

        uploaded = st.file_uploader("Choose CSV", type=["csv"])
        if uploaded is not None:
            try:
                up_df = pd.read_csv(uploaded)
                required = {"ts", "cpu", "ram", "disk", "latency_ms"}
                missing = required - set(up_df.columns)
                if missing:
                    st.error(f"Missing columns: {sorted(missing)}")
                else:
                    # normalize ts
                    up_df["ts"] = pd.to_datetime(up_df["ts"], errors="coerce")
                    if up_df["ts"].isna().any():
                        st.warning("Some ts values could not be parsed. Check your CSV timestamps.")
                    st.session_state.df = up_df
                    st.success(f"Loaded CSV with {len(up_df)} rows.")
            except Exception as e:
                st.error(f"CSV load failed: {e}")

    st.divider()

    if df is None or len(df) == 0:
        st.info("Generate sample data above, or upload a CSV to begin.")
        st.stop()

    st.subheader("Preview")
    st.dataframe(df.head(60), use_container_width=True)

    st.subheader("Metric Charts")
    try:
        chart_df = df.copy()
        chart_df["ts"] = pd.to_datetime(chart_df["ts"])
        chart_df = chart_df.set_index("ts")[["cpu", "ram", "disk", "latency_ms"]]
        st.line_chart(chart_df, use_container_width=True)
    except Exception as e:
        st.warning(f"Chart render failed: {e}")

    st.subheader("Detection (saves to SQLite)")

    contamination = st.slider(
        "Sensitivity (contamination)",
        min_value=0.01,
        max_value=0.20,
        value=0.03,
        step=0.01,
        help="Higher = more anomalies flagged.",
    )
    st.caption(f"Expected anomalies (roughly): ~{int(len(df) * contamination)} out of {len(df)} points")

    payload = {
        "points": ensure_ts_str(df).to_dict(orient="records"),
        "contamination": float(contamination),
    }

    if st.button("Detect anomalies", type="primary"):
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
            st.markdown("### Anomalies (sorted by score)")
            if "score" in anomalies.columns:
                anomalies = anomalies.sort_values("score", ascending=False)
            st.dataframe(anomalies, use_container_width=True)

# ---------------------------
# Run History tab
# ---------------------------
with tab_history:
    st.subheader("Saved Runs (from logsense.db)")

    # Derive base URL from /detect endpoint
    base_url = api_url.rsplit("/", 1)[0] if "/" in api_url else api_url
    runs_url = f"{base_url}/runs"
    run_url = f"{base_url}/runs/{{run_id}}"

    try:
        r = requests.get(runs_url, timeout=30)
        r.raise_for_status()
        runs = r.json().get("runs", [])
    except Exception as e:
        st.error(f"Failed to load runs: {e}")
        st.stop()

    if not runs:
        st.info("No saved runs yet. Go to Detect tab and run detection once.")
        st.stop()

    runs_df = pd.DataFrame(runs)
    st.dataframe(runs_df, use_container_width=True)

    run_id = st.number_input("Enter run_id to view anomalies", min_value=1, value=int(runs_df["id"].max()))
    try:
        r2 = requests.get(run_url.format(run_id=int(run_id)), timeout=30)
        r2.raise_for_status()
        run_detail = r2.json()
    except Exception as e:
        st.error(f"Failed to load run {run_id}: {e}")
        st.stop()

    st.markdown(f"### Anomalies for run {run_id}")
    anoms = pd.DataFrame(run_detail.get("anomalies", []))
    if len(anoms) == 0:
        st.info("No anomalies for this run.")
    else:
        if "score" in anoms.columns:
            anoms = anoms.sort_values("score", ascending=False)
        st.dataframe(anoms, use_container_width=True)

