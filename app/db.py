"""
LogSense SQLite Persistence
Author: Ali Bidhendi

Stores:
- runs: each detection request
- anomalies: anomaly rows for each run
"""

import sqlite3
from typing import List, Dict, Any

DB_PATH = "logsense.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        total_points INTEGER NOT NULL,
        anomalies_found INTEGER NOT NULL
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS anomalies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER NOT NULL,
        ts TEXT NOT NULL,
        score REAL NOT NULL,
        fields TEXT NOT NULL,
        note TEXT NOT NULL,
        FOREIGN KEY(run_id) REFERENCES runs(id)
    )
    """)

    conn.commit()
    conn.close()

def save_run(created_at: str, total_points: int, anomalies_found: int) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO runs (created_at, total_points, anomalies_found) VALUES (?, ?, ?)",
        (created_at, total_points, anomalies_found),
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return int(run_id)

def save_anomalies(run_id: int, anomalies: List[Dict[str, Any]]):
    conn = get_conn()
    cur = conn.cursor()
    for a in anomalies:
        cur.execute(
            "INSERT INTO anomalies (run_id, ts, score, fields, note) VALUES (?, ?, ?, ?, ?)",
            (run_id, a["ts"], float(a["score"]), ",".join(a["fields"]), a["note"]),
        )
    conn.commit()
    conn.close()

def list_runs(limit: int = 25):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, created_at, total_points, anomalies_found FROM runs ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def get_anomalies_for_run(run_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT ts, score, fields, note FROM anomalies WHERE run_id = ? ORDER BY score DESC",
        (run_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows
