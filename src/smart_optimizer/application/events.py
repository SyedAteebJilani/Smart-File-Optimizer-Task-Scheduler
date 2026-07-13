from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from smart_optimizer.domain.models import ScanEvent


class QtEventBridge(QObject):
    scan_started = pyqtSignal(object)
    scan_finished = pyqtSignal(object)
    metrics_updated = pyqtSignal(object)
    scheduler_updated = pyqtSignal(object)
    workers_updated = pyqtSignal(object)
    duplicates_updated = pyqtSignal(object)
    job_completed = pyqtSignal(object)
    file_deleted = pyqtSignal(object)
    error_reported = pyqtSignal(object)

    def publish(self, event: ScanEvent) -> None:
        payload = _serialize(event.payload)
        if event.name == "scan_started":
            self.scan_started.emit(payload)
        elif event.name == "scan_finished":
            self.scan_finished.emit(payload)
        elif event.name == "metrics_updated":
            self.metrics_updated.emit(payload)
        elif event.name == "scheduler_updated":
            self.scheduler_updated.emit(payload)
        elif event.name == "workers_updated":
            self.workers_updated.emit(payload)
        elif event.name == "duplicates_updated":
            self.duplicates_updated.emit(payload)
        elif event.name == "duplicate_group_updated":
            self.duplicates_updated.emit(payload)
        elif event.name == "job_completed":
            self.job_completed.emit(payload)
        elif event.name == "file_deleted":
            self.file_deleted.emit(payload)
        elif event.name == "error":
            self.error_reported.emit(payload)


def _serialize(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value
