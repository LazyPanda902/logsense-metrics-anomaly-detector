from pydantic import BaseModel
from typing import List, Optional

class MetricPoint(BaseModel):
    ts: str  # ISO time string
    cpu: float
    ram: float
    disk: float
    latency_ms: float

class IngestRequest(BaseModel):
    points: List[MetricPoint]

class Anomaly(BaseModel):
    ts: str
    score: float
    fields: List[str]
    note: str

class DetectResponse(BaseModel):
    total_points: int
    anomalies_found: int
    anomalies: List[Anomaly]
