from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import asdict, replace
from pathlib import Path
from uuid import uuid4

from smart_optimizer.application.events import QtEventBridge
from smart_optimizer.domain.interfaces import (
    DuplicateRepository,
    FileSystemScanner,
    LearningRepository,
    ScanHistoryRepository,
)
from smart_optimizer.domain.models import FileRecord, ScanEvent, ScanJob, ScanRequest, ScanSummary, utc_now
from smart_optimizer.domain.risk import is_path_near_system_area
from smart_optimizer.infrastructure.duplicates import ThreadSafeDuplicateIndex
from smart_optimizer.infrastructure.hashing import Sha256FileHasher
from smart_optimizer.infrastructure.metrics import MetricsTracker
from smart_optimizer.infrastructure.scheduler import AgingPriorityScheduler
from smart_optimizer.infrastructure.thread_pool import FixedWorkerPool


MAX_WORKER_THREADS = 3


class ScanCancelled(RuntimeError):
    pass


class ScanController:
    def __init__(
        self,
        scanner: FileSystemScanner,
        duplicate_index: ThreadSafeDuplicateIndex,
        hasher: Sha256FileHasher,
        history_repository: ScanHistoryRepository,
        duplicate_repository: DuplicateRepository,
        learning_repository: LearningRepository,
        metrics: MetricsTracker,
        event_bridge: QtEventBridge,
        logger: logging.Logger,
    ) -> None:
        self._scanner = scanner
        self._duplicate_index = duplicate_index
        self._hasher = hasher
        self._history_repository = history_repository
        self._duplicate_repository = duplicate_repository
        self._learning_repository = learning_repository
        self._metrics = metrics
        self._events = event_bridge
        self._logger = logger
        self._lock = threading.RLock()
        self._active = False
        self._stop_event = threading.Event()
        self._scan_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._scheduler: AgingPriorityScheduler | None = None
        self._pool: FixedWorkerPool | None = None
        self._active_scan_id: str | None = None
        self._submitted_jobs = 0
        self._failed_discovery_errors = 0
        self._learned_folder_counts: dict[Path, int] = {}

    def start_scan(self, root_path: str, include_hidden: bool, max_workers: int) -> None:
        with self._lock:
            if self._active:
                self._events.publish(
                    ScanEvent("error", {"message": "A scan is already running."})
                )
                return
            root = Path(root_path)
            if not root.exists() or not root.is_dir():
                self._events.publish(
                    ScanEvent("error", {"message": f"Invalid scan directory: {root_path}"})
                )
                return

            request = ScanRequest(root, include_hidden, max(1, min(max_workers, MAX_WORKER_THREADS)))
            self._active = True
            self._stop_event.clear()
            self._active_scan_id = request.request_id
            self._submitted_jobs = 0
            self._failed_discovery_errors = 0
            self._learned_folder_counts = self._learning_repository.folder_duplicate_counts()
            self._duplicate_index.reset()
            self._metrics.reset_for_scan()
            self._history_repository.create_scan(request)
            self._scheduler = AgingPriorityScheduler()
            self._pool = FixedWorkerPool(
                request.max_workers,
                self._scheduler,
                self._duplicate_index,
                self._hasher,
                self._metrics,
                self._events,
                self._logger,
                self._publish_duplicate_snapshot,
            )
            self._pool.start()
            self._scan_thread = threading.Thread(
                target=self._run_scan,
                args=(request,),
                name="scan-producer",
                daemon=True,
            )
            self._monitor_thread = threading.Thread(
                target=self._monitor,
                name="scan-monitor",
                daemon=True,
            )
            self._scan_thread.start()
            self._monitor_thread.start()
            self._events.publish(
                ScanEvent(
                    "scan_started",
                    {
                        "scan_id": request.request_id,
                        "root_path": str(request.root_path),
                        "workers": request.max_workers,
                    },
                )
            )

    def stop_scan(self) -> None:
        with self._lock:
            self._stop_event.set()
            if self._scheduler is not None:
                self._scheduler.shutdown()

    def shutdown(self) -> None:
        self.stop_scan()
        with self._lock:
            pool = self._pool
        if pool is not None:
            pool.stop()

    def recent_scans(self, limit: int = 20) -> list[ScanSummary]:
        return self._history_repository.list_recent_scans(limit)

    def delete_duplicate_file(
        self,
        path_text: str,
        size_bytes: int,
        risk_score: int,
    ) -> tuple[bool, str]:
        path = Path(path_text)
        try:
            if not path.exists():
                return False, "The file is no longer available."
            if path.is_dir():
                return False, "Folders cannot be deleted from duplicate actions."
            self._move_to_recycle_bin(path)
            self._learning_repository.record_deletion(path, size_bytes, risk_score)
            self._events.publish(
                ScanEvent(
                    "file_deleted",
                    {
                        "path": str(path),
                        "size_bytes": size_bytes,
                        "risk_score": risk_score,
                    },
                )
            )
            return True, "File moved to Recycle Bin."
        except Exception as exc:
            self._logger.warning("Unable to delete duplicate %s: %s", path, exc)
            return False, f"Delete failed: {exc}"

    @staticmethod
    def _move_to_recycle_bin(path: Path) -> None:
        if os.name != "nt":
            path.unlink()
            return

        import ctypes
        from ctypes import wintypes

        class SHFILEOPSTRUCTW(ctypes.Structure):
            _fields_ = [
                ("hwnd", wintypes.HWND),
                ("wFunc", wintypes.UINT),
                ("pFrom", wintypes.LPCWSTR),
                ("pTo", wintypes.LPCWSTR),
                ("fFlags", wintypes.USHORT),
                ("fAnyOperationsAborted", wintypes.BOOL),
                ("hNameMappings", wintypes.LPVOID),
                ("lpszProgressTitle", wintypes.LPCWSTR),
            ]

        operation = SHFILEOPSTRUCTW()
        operation.hwnd = None
        operation.wFunc = 3
        operation.pFrom = f"{path}\0\0"
        operation.pTo = None
        operation.fFlags = 0x0040 | 0x0400 | 0x0004
        result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))  # type: ignore[attr-defined]
        if result != 0 or operation.fAnyOperationsAborted:
            raise OSError(f"Windows recycle operation failed with code {result}")

    def _run_scan(self, request: ScanRequest) -> None:
        started_at = request.created_at
        summary = ScanSummary(
            scan_id=request.request_id,
            root_path=request.root_path,
            started_at=started_at,
            finished_at=None,
            files_discovered=0,
            files_processed=0,
            duplicate_groups=0,
            reclaimable_bytes=0,
            errors=0,
        )
        try:
            scan_summary = self._scanner.scan(request, self._on_file_discovered)
            self._failed_discovery_errors = scan_summary.errors
            self._wait_for_workers_to_drain()
            groups = self._duplicate_index.groups()
            for group in groups:
                self._learning_repository.record_duplicate_group(group)
            reclaimable = sum(group.reclaimable_bytes for group in groups)
            metrics_snapshot = self._metrics.snapshot()
            summary = replace(
                scan_summary,
                finished_at=utc_now(),
                files_processed=metrics_snapshot.files_processed,
                duplicate_groups=len(groups),
                reclaimable_bytes=reclaimable,
                errors=scan_summary.errors + metrics_snapshot.files_failed,
            )
            self._duplicate_repository.replace_groups(request.request_id, groups)
            self._history_repository.finish_scan(summary)
            self._metrics.finish_scan()
            self._publish_duplicate_snapshot()
            self._events.publish(ScanEvent("scan_finished", asdict(summary)))
        except ScanCancelled:
            groups = self._duplicate_index.groups()
            summary = replace(
                summary,
                finished_at=utc_now(),
                files_processed=self._metrics.snapshot().files_processed,
                duplicate_groups=len(groups),
                reclaimable_bytes=sum(group.reclaimable_bytes for group in groups),
                errors=summary.errors,
            )
            self._duplicate_repository.replace_groups(request.request_id, groups)
            self._history_repository.finish_scan(summary)
            self._metrics.finish_scan()
            self._events.publish(ScanEvent("scan_finished", asdict(summary)))
        except Exception as exc:
            self._logger.exception("Scan failed")
            failed_summary = replace(summary, finished_at=utc_now(), errors=summary.errors + 1)
            self._history_repository.finish_scan(failed_summary)
            self._events.publish(ScanEvent("error", {"message": f"Scan failed: {exc}"}))
        finally:
            with self._lock:
                if self._pool is not None:
                    self._pool.stop()
                self._active = False
                self._scheduler = None
                self._pool = None
                self._active_scan_id = None

    def _on_file_discovered(self, record: FileRecord) -> None:
        if self._stop_event.is_set():
            raise ScanCancelled()
        self._metrics.file_discovered()
        candidates = self._duplicate_index.register_file(record)
        for candidate in candidates:
            self._submit_candidate(candidate)

    def _submit_candidate(self, record: FileRecord) -> None:
        scheduler = self._scheduler
        if scheduler is None:
            return
        priority = self._priority_for(record)
        job = ScanJob(
            job_id=str(uuid4()),
            file_path=record.path,
            size_bytes=record.size_bytes,
            modified_at=record.modified_at,
            extension=record.extension,
            is_hidden=record.is_hidden,
            is_system=record.is_system,
            base_priority=priority,
            effective_priority=priority,
            created_at=time.monotonic(),
        )
        with self._lock:
            self._submitted_jobs += 1
        scheduler.submit(job)

    def _priority_for(self, record: FileRecord) -> int:
        learned_boost = self._learned_folder_counts.get(record.path.parent, 0)
        priority = 5
        if learned_boost > 5:
            priority = 1
        if record.size_bytes > 100 * 1024 * 1024:
            priority = min(priority, 2)
        if is_path_near_system_area(record.path) or record.is_system:
            priority = min(priority + 2, 9)
        return priority

    def _wait_for_workers_to_drain(self) -> None:
        while not self._stop_event.is_set():
            scheduler = self._scheduler
            if scheduler is None:
                return
            snapshot = scheduler.snapshot()
            if snapshot.queued == 0 and snapshot.running == 0:
                return
            time.sleep(0.2)

    def _monitor(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                scheduler = self._scheduler
                pool = self._pool
                active = self._active
            if not active:
                return
            if scheduler is not None:
                scheduler_snapshot = scheduler.snapshot()
                self._metrics.set_scheduler_metrics(
                    scheduler_snapshot.queued,
                    scheduler_snapshot.average_wait_ms,
                )
                self._events.publish(ScanEvent("scheduler_updated", asdict(scheduler_snapshot)))
            if pool is not None:
                workers = pool.snapshots()
                running = sum(1 for worker in workers if worker.state.value == "Running")
                self._metrics.set_thread_utilization(running / max(1, len(workers)))
            self._publish_metrics_snapshot()
            time.sleep(0.5)

    def _publish_metrics_snapshot(self) -> None:
        groups = self._duplicate_index.groups()
        duplicate_files = sum(len(group.files) for group in groups)
        reclaimable = sum(group.reclaimable_bytes for group in groups)
        self._metrics.set_duplicate_metrics(duplicate_files, reclaimable)
        self._events.publish(ScanEvent("metrics_updated", asdict(self._metrics.snapshot())))

    def _publish_duplicate_snapshot(self) -> None:
        groups = self._duplicate_index.groups()
        self._events.publish(
            ScanEvent(
                "duplicates_updated",
                {
                    "groups": [
                        {
                            "group_id": group.group_id,
                            "full_hash": group.full_hash,
                            "size_bytes": group.size_bytes,
                            "risk_score": group.risk_score,
                            "risk_level": group.risk_level.value,
                            "reclaimable_bytes": group.reclaimable_bytes,
                            "files": [
                                {
                                    "path": str(file.path),
                                    "size_bytes": file.size_bytes,
                                    "extension": file.extension,
                                    "modified_at": file.modified_at,
                                    "is_hidden": file.is_hidden,
                                    "is_system": file.is_system,
                                }
                                for file in group.files
                            ],
                        }
                        for group in sorted(groups, key=lambda item: item.risk_score, reverse=True)
                    ]
                },
            )
        )
