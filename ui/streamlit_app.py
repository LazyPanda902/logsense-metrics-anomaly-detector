import os, sys
import streamlit as st
import pandas as pd
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

st.set_page_config(page_title="LogSense Dashboard", layout="wide")
st.title("LogSense: Metrics Anomaly Detector")
st.caption("By Ali Bidhendi")

api_url = st.text_input("API URL", value="http://localhost:8000/detect")

st.subheader("Upload metrics CSV")
st.write("Required columns: ts,cpu,ram,disk,latency_ms")

file = st.file_uploader("Choose CSV", type=["csv"])

if file:
    df = pd.read_csv(file)

    # Basic validation
    required = {"ts", "cpu", "ram", "disk", "latency_ms"}
    missing = required - set(df.columns)
    if missing:
        st.error(f"Missing columns: {sorted(list(missing))}")
        st.stop()

    # Sort by time for clean charts
    df = df.copy()
    df["ts"] = df["ts"].astype(str)
    df = df.sort_values("ts")

    left, right = st.columns([1.2, 1])

    with left:
        st.markdown("### Preview")
        st.dataframe(df.head(50), use_container_width=True)

        st.markdown("### Metric Charts")
        chart_df = df.set_index("ts")[["cpu", "ram", "disk", "latency_ms"]]
        st.line_chart(chart_df, use_container_width=True)

    with right:
        st.markdown("### Detection Settings")
        st.write("This MVP trains IsolationForest on the uploaded batch.")

        if st.button("Detect anomalies", type="primary"):
            payload = {"points": df.to_dict(orient="records")}
            r = requests.post(api_url, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()

            st.success("Detection complete.")
            st.metric("Total points", data["total_points"])
            st.metric("Anomalies found", data["anomalies_found"])

            anomalies = pd.DataFrame(data["anomalies"])

            if len(anomalies) == 0:
                st.info("No anomalies found in this batch.")
            else:
                st.markdown("### Anomalies (sorted by score)")
                anomalies = anomalies.sort_values("score", ascending=False)

                st.dataframe(anomalies, use_container_width=True)

                # Highlight anomalies on the original df
                st.markdown("### Rows flagged as anomalies")
                flagged_ts = set(anomalies["ts"].astype(str).tolist())
                flagged = df[df["ts"].astype(str).isin(flagged_ts)].copy()
                st.dataframe(flagged, use_container_width=True)

                # Download anomalies as CSV
                csv_bytes = anomalies.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download anomalies.csv",
                    data=csv_bytes,
                    file_name="anomalies.csv",
                    mime="text/csv",
                )
else:
    st.info("Upload a CSV to begin. Try: data/sample_metrics.csv")

