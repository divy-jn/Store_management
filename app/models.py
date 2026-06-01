"""
Pydantic models for the Store Intelligence API.
Covers event schemas, request/response models for all endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for API response defaults."""
    return datetime.now(timezone.utc)


# ─────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────


class EventType(str, Enum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"


class AnomalySeverity(str, Enum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class AnomalyType(str, Enum):
    BILLING_QUEUE_SPIKE = "BILLING_QUEUE_SPIKE"
    CONVERSION_DROP = "CONVERSION_DROP"
    DEAD_ZONE = "DEAD_ZONE"
    STALE_FEED = "STALE_FEED"


# ─────────────────────────────────────────────
# Event Schema (Detection Pipeline Output)
# ─────────────────────────────────────────────


class EventMetadata(BaseModel):
    """Metadata attached to each event."""

    queue_depth: Optional[int] = None
    sku_zone: Optional[str] = None
    session_seq: Optional[int] = None


class Event(BaseModel):
    """
    Core event schema emitted by the detection pipeline.
    Matches the required output schema from the problem statement.
    """

    event_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Globally unique UUID v4 identifier",
    )
    store_id: str = Field(
        ..., description="Store identifier from store_layout.json", examples=["ST1008"]
    )
    camera_id: str = Field(
        ..., description="Camera that produced this event", examples=["CAM_ENTRY_01"]
    )
    visitor_id: str = Field(
        ...,
        description="Re-ID token — unique per visit session",
        examples=["VIS_c8a2f1"],
    )
    event_type: EventType = Field(..., description="Type of behavioral event")
    timestamp: datetime = Field(..., description="ISO-8601 UTC timestamp")
    zone_id: Optional[str] = Field(
        None,
        description="Zone identifier — null for ENTRY/EXIT events",
        examples=["SKINCARE", "BILLING"],
    )
    dwell_ms: int = Field(
        0, ge=0, description="Duration in milliseconds; 0 for instantaneous events"
    )
    is_staff: bool = Field(False, description="Whether this person is store staff")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Detection confidence score (0.0 to 1.0)"
    )
    metadata: EventMetadata = Field(
        default_factory=EventMetadata, description="Additional event metadata"
    )


# ─────────────────────────────────────────────
# Ingest Endpoint Models
# ─────────────────────────────────────────────


class IngestRequest(BaseModel):
    """Batch of events to ingest (max 500)."""

    events: list[Event] = Field(
        ..., max_length=500, description="Batch of up to 500 events"
    )


class EventError(BaseModel):
    """Error detail for a single event that failed validation."""

    event_id: Optional[str] = None
    index: int
    error: str


class IngestResponse(BaseModel):
    """Response from POST /events/ingest."""

    accepted: int = Field(description="Number of events successfully ingested")
    rejected: int = Field(description="Number of events that failed validation")
    duplicates: int = Field(0, description="Number of duplicate events skipped")
    errors: list[EventError] = Field(
        default_factory=list, description="Details of rejected events"
    )


# ─────────────────────────────────────────────
# Metrics Endpoint Models
# ─────────────────────────────────────────────


class ZoneDwell(BaseModel):
    """Average dwell time for a specific zone."""

    zone_id: str
    zone_name: str
    avg_dwell_ms: float
    visit_count: int


class MetricsResponse(BaseModel):
    """Response from GET /stores/{id}/metrics."""

    store_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    unique_visitors: int = Field(description="Unique non-staff visitors today")
    conversion_rate: float = Field(
        description="Visitors who purchased / total visitors (0.0 to 1.0)"
    )
    avg_dwell_per_zone: list[ZoneDwell] = Field(
        default_factory=list, description="Average dwell time per zone"
    )
    current_queue_depth: int = Field(0, description="Current billing queue depth")
    abandonment_rate: float = Field(
        0.0, description="Queue abandonment rate (0.0 to 1.0)"
    )
    total_entries: int = 0
    total_exits: int = 0


# ─────────────────────────────────────────────
# Funnel Endpoint Models
# ─────────────────────────────────────────────


class FunnelStage(BaseModel):
    """A single stage in the conversion funnel."""

    stage: str
    count: int
    percentage: float = Field(description="Percentage relative to Entry stage")
    drop_off_percent: float = Field(0.0, description="Drop-off from previous stage")


class FunnelResponse(BaseModel):
    """Response from GET /stores/{id}/funnel."""

    store_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    stages: list[FunnelStage]
    total_sessions: int


# ─────────────────────────────────────────────
# Heatmap Endpoint Models
# ─────────────────────────────────────────────


class ZoneHeatmapEntry(BaseModel):
    """Heatmap data for a single zone."""

    zone_id: str
    zone_name: str
    visit_count: int
    avg_dwell_ms: float
    normalized_score: float = Field(ge=0, le=100, description="Normalized 0-100 score")
    data_confidence: str = Field(
        "high", description="'high' if >= 20 sessions, 'low' otherwise"
    )


class HeatmapResponse(BaseModel):
    """Response from GET /stores/{id}/heatmap."""

    store_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    zones: list[ZoneHeatmapEntry]
    total_sessions: int


# ─────────────────────────────────────────────
# Anomalies Endpoint Models
# ─────────────────────────────────────────────


class Anomaly(BaseModel):
    """A single detected anomaly."""

    anomaly_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    description: str
    suggested_action: str
    detected_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnomaliesResponse(BaseModel):
    """Response from GET /stores/{id}/anomalies."""

    store_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    anomalies: list[Anomaly]
    active_count: int


# ─────────────────────────────────────────────
# Health Endpoint Models
# ─────────────────────────────────────────────


class StoreHealth(BaseModel):
    """Health status for a single store."""

    store_id: str
    last_event_at: Optional[datetime] = None
    event_count: int = 0
    is_stale: bool = False
    stale_warning: Optional[str] = None


class HealthResponse(BaseModel):
    """Response from GET /health."""

    status: str = Field(
        description="Service status: 'healthy', 'degraded', 'unhealthy'"
    )
    uptime_seconds: float
    database_connected: bool
    stores: list[StoreHealth] = Field(default_factory=list)
    last_event_at: Optional[datetime] = None
    version: str = "1.0.0"
