from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4


class JobState(str, Enum):
    QUEUED = "Queued"
    READY = "Ready"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"


class WorkerState(str, Enum):
    WAITING = "Waiting"
    RUNNING = "Running"
    BLOCKED = "Blocked"
    STOPPED = "Stopped"


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class ScanRequest:
    root_path: Path
    include_hidden: bool
    max_workers: int
    created_at: datetime = field(default_factory=utc_now)
    request_id: str = field(default_factory=lambda: str(uuid4()))


@dataclass(slots=True)
class ScanJob:
    job_id: str
    file_path: Path
    size_bytes: int
    modified_at: float
    extension: str
    is_hidden: bool
    is_system: bool
    base_priority: int
    effective_priority: int
    created_at: float
    state: JobState = JobState.QUEUED
    attempts: int = 0
    error: str | None = None


@dataclass(frozen=True, slots=True)
class FileRecord:
    path: Path
    size_bytes: int
    modified_at: float
    extension: str
    is_hidden: bool
    is_system: bool
    partial_hash: str | None = None
    full_hash: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class DuplicateGroup:
    group_id: str
    full_hash: str
    size_bytes: int
    files: tuple[FileRecord, ...]
    risk_score: int
    risk_level: RiskLevel
    reclaimable_bytes: int


@dataclass(frozen=True, slots=True)
class WorkerSnapshot:
    worker_id: int
    state: WorkerState
    current_job_id: str | None
    current_file: str | None
    processed_count: int
    failed_count: int
    busy_seconds: float


@dataclass(frozen=True, slots=True)
class SchedulerSnapshot:
    queued: int
    ready: int
    running: int
    completed: int
    failed: int
    average_wait_ms: float
    boosted_jobs: int
    oldest_wait_ms: float


@dataclass(frozen=True, slots=True)
class MetricsSnapshot:
    files_discovered: int
    files_processed: int
    files_failed: int
    files_per_second: float
    queue_depth: int
    thread_utilization: float
    average_queue_wait_ms: float
    memory_usage_mb: float
    storage_reclaimable_bytes: int
    average_scan_duration_seconds: float
    duplicate_density: float
    active_scan_seconds: float


@dataclass(frozen=True, slots=True)
class ScanSummary:
    scan_id: str
    root_path: Path
    started_at: datetime
    finished_at: datetime | None
    files_discovered: int
    files_processed: int
    duplicate_groups: int
    reclaimable_bytes: int
    errors: int


@dataclass(frozen=True, slots=True)
class ScanEvent:
    name: str
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=utc_now)
