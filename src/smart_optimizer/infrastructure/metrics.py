from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque

try:
    import psutil
except ImportError:  # pragma: no cover - runtime dependency path
    psutil = None  # type: ignore[assignment]

from smart_optimizer.domain.models import MetricsSnapshot


@dataclass(slots=True)
class _ScanTiming:
    started_at: float
    finished_at: float | None = None


class MetricsTracker:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._files_discovered = 0
        self._files_processed = 0
        self._files_failed = 0
        self._storage_reclaimable_bytes = 0
        self._duplicate_files = 0
        self._queue_depth = 0
        self._thread_utilization = 0.0
        self._average_queue_wait_ms = 0.0
        self._active_scan_started_at: float | None = None
        self._scan_timings: Deque[_ScanTiming] = deque(maxlen=100)
        self._processed_samples: Deque[tuple[float, int]] = deque(maxlen=20)

    def reset_for_scan(self) -> None:
        with self._lock:
            now = time.monotonic()
            self._files_discovered = 0
            self._files_processed = 0
            self._files_failed = 0
            self._storage_reclaimable_bytes = 0
            self._duplicate_files = 0
            self._queue_depth = 0
            self._thread_utilization = 0.0
            self._average_queue_wait_ms = 0.0
            self._active_scan_started_at = now
            self._scan_timings.append(_ScanTiming(started_at=now))
            self._processed_samples.clear()
            self._processed_samples.append((now, 0))

    def finish_scan(self) -> None:
        with self._lock:
            now = time.monotonic()
            self._active_scan_started_at = None
            if self._scan_timings and self._scan_timings[-1].finished_at is None:
                self._scan_timings[-1].finished_at = now

    def file_discovered(self) -> None:
        with self._lock:
            self._files_discovered += 1

    def file_processed(self) -> None:
        with self._lock:
            self._files_processed += 1
            self._processed_samples.append((time.monotonic(), self._files_processed))

    def file_failed(self) -> None:
        with self._lock:
            self._files_failed += 1

    def set_scheduler_metrics(self, queue_depth: int, average_wait_ms: float) -> None:
        with self._lock:
            self._queue_depth = queue_depth
            self._average_queue_wait_ms = average_wait_ms

    def set_thread_utilization(self, utilization: float) -> None:
        with self._lock:
            self._thread_utilization = max(0.0, min(1.0, utilization))

    def set_duplicate_metrics(self, duplicate_files: int, reclaimable_bytes: int) -> None:
        with self._lock:
            self._duplicate_files = duplicate_files
            self._storage_reclaimable_bytes = reclaimable_bytes

    def snapshot(self) -> MetricsSnapshot:
        with self._lock:
            files_per_second = self._calculate_rate_locked()
            memory_usage_mb = self._memory_usage_mb()
            completed_durations = [
                timing.finished_at - timing.started_at
                for timing in self._scan_timings
                if timing.finished_at is not None
            ]
            avg_duration = (
                sum(completed_durations) / len(completed_durations)
                if completed_durations
                else 0.0
            )
            duplicate_density = (
                self._duplicate_files / self._files_processed
                if self._files_processed > 0
                else 0.0
            )
            active_seconds = (
                time.monotonic() - self._active_scan_started_at
                if self._active_scan_started_at is not None
                else 0.0
            )
            return MetricsSnapshot(
                files_discovered=self._files_discovered,
                files_processed=self._files_processed,
                files_failed=self._files_failed,
                files_per_second=files_per_second,
                queue_depth=self._queue_depth,
                thread_utilization=self._thread_utilization,
                average_queue_wait_ms=self._average_queue_wait_ms,
                memory_usage_mb=memory_usage_mb,
                storage_reclaimable_bytes=self._storage_reclaimable_bytes,
                average_scan_duration_seconds=avg_duration,
                duplicate_density=duplicate_density,
                active_scan_seconds=active_seconds,
            )

    def _calculate_rate_locked(self) -> float:
        if len(self._processed_samples) < 2:
            return 0.0
        oldest_time, oldest_count = self._processed_samples[0]
        newest_time, newest_count = self._processed_samples[-1]
        elapsed = newest_time - oldest_time
        if elapsed <= 0:
            return 0.0
        return (newest_count - oldest_count) / elapsed

    @staticmethod
    def _memory_usage_mb() -> float:
        if psutil is None:
            return 0.0
        return float(psutil.Process().memory_info().rss / (1024 * 1024))

