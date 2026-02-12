import os, sys
import streamlit as st
import pandas as pd
import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

st.title("LogSense: Metrics Anomaly Detector")
st.caption("By Ali Bidhendi")

api_url = st.text_input("API URL", value="http://localhost:8000/detect")

st.subheader("Upload metrics CSV")
st.write("CSV columns: ts,cpu,ram,disk,latency_ms")

file = st.file_uploader("Choose CSV", type=["csv"])

if file:
    df = pd.read_csv(file)
    st.dataframe(df.head(20))

    if st.button("Detect anomalies"):
        payload = {"points": df.to_dict(orient="records")}
        r = requests.post(api_url, json=payload, timeout=60)
        r.raise_for_status()
        data = r.json()

        st.metric("Total points", data["total_points"])
        st.metric("Anomalies found", data["anomalies_found"])
        st.write(data["anomalies"])
