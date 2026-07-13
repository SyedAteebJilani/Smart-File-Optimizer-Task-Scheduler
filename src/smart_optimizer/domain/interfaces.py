from __future__ import annotations

from pathlib import Path
from typing import Callable, Protocol

from smart_optimizer.domain.models import (
    DuplicateGroup,
    FileRecord,
    MetricsSnapshot,
    ScanEvent,
    ScanJob,
    ScanRequest,
    ScanSummary,
    SchedulerSnapshot,
    WorkerSnapshot,
)


class EventPublisher(Protocol):
    def publish(self, event: ScanEvent) -> None:
        ...


class FileSystemScanner(Protocol):
    def scan(self, request: ScanRequest, on_file: Callable[[FileRecord], None]) -> ScanSummary:
        ...


class FileHasher(Protocol):
    def partial_hash(self, path: Path) -> str:
        ...

    def full_hash(self, path: Path) -> str:
        ...


class DuplicateIndex(Protocol):
    def register_file(self, record: FileRecord) -> list[FileRecord]:
        ...

    def accept_partial_hash(self, record: FileRecord) -> list[FileRecord]:
        ...

    def accept_full_hash(self, record: FileRecord) -> list[DuplicateGroup]:
        ...

    def groups(self) -> list[DuplicateGroup]:
        ...

    def reset(self) -> None:
        ...


class JobScheduler(Protocol):
    def submit(self, job: ScanJob) -> None:
        ...

    def acquire(self, timeout: float) -> ScanJob | None:
        ...

    def complete(self, job: ScanJob, error: str | None = None) -> None:
        ...

    def snapshot(self) -> SchedulerSnapshot:
        ...

    def shutdown(self) -> None:
        ...


class WorkerPool(Protocol):
    def start(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def snapshots(self) -> list[WorkerSnapshot]:
        ...


class ScanHistoryRepository(Protocol):
    def create_scan(self, request: ScanRequest) -> str:
        ...

    def finish_scan(self, summary: ScanSummary) -> None:
        ...

    def list_recent_scans(self, limit: int) -> list[ScanSummary]:
        ...


class DuplicateRepository(Protocol):
    def replace_groups(self, scan_id: str, groups: list[DuplicateGroup]) -> None:
        ...

    def load_groups(self, scan_id: str) -> list[DuplicateGroup]:
        ...


class LearningRepository(Protocol):
    def record_duplicate_group(self, group: DuplicateGroup) -> None:
        ...

    def record_deletion(self, path: Path, size_bytes: int, risk_score: int) -> None:
        ...

    def ignored_directories(self) -> set[Path]:
        ...

    def folder_duplicate_counts(self) -> dict[Path, int]:
        ...

    def deletion_patterns(self) -> dict[str, int]:
        ...


class MetricsProvider(Protocol):
    def snapshot(self) -> MetricsSnapshot:
        ...
