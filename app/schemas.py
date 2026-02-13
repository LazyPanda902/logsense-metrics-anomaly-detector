"""
LogSense Schemas (Pydantic)
Author: Ali Bidhendi

This file defines the request/response models for the API.
We added `contamination` to let the UI control sensitivity.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class MetricPoint(BaseModel):
    ts: str
    cpu: float
    ram: float
    disk: float
    latency_ms: float


class IngestRequest(BaseModel):
    points: List[MetricPoint]

    # contamination ~= expected fraction of anomalies
    # Example: 0.05 with 240 points => ~12 anomalies
    contamination: float = Field(default=0.05, ge=0.01, le=0.30)


class Anomaly(BaseModel):
    ts: str
    score: float
    fields: List[str]
    note: str


class DetectResponse(BaseModel):
    total_points: int
    anomalies_found: int
    anomalies: List[Anomaly]

