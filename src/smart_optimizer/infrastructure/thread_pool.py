from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, replace
from typing import Callable

from smart_optimizer.domain.interfaces import EventPublisher
from smart_optimizer.domain.models import ScanEvent, ScanJob, WorkerSnapshot, WorkerState
from smart_optimizer.infrastructure.duplicates import ThreadSafeDuplicateIndex
from smart_optimizer.infrastructure.hashing import Sha256FileHasher
from smart_optimizer.infrastructure.metrics import MetricsTracker
from smart_optimizer.infrastructure.scheduler import AgingPriorityScheduler


class FixedWorkerPool:
    def __init__(
        self,
        worker_count: int,
        scheduler: AgingPriorityScheduler,
        duplicate_index: ThreadSafeDuplicateIndex,
        hasher: Sha256FileHasher,
        metrics: MetricsTracker,
        publisher: EventPublisher,
        logger: logging.Logger,
        on_group_changed: Callable[[], None],
    ) -> None:
        self._worker_count = max(1, worker_count)
        self._scheduler = scheduler
        self._duplicate_index = duplicate_index
        self._hasher = hasher
        self._metrics = metrics
        self._publisher = publisher
        self._logger = logger
        self._on_group_changed = on_group_changed
        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()
        self._threads: list[threading.Thread] = []
        self._states: dict[int, WorkerSnapshot] = {
            worker_id: WorkerSnapshot(worker_id, WorkerState.WAITING, None, None, 0, 0, 0.0)
            for worker_id in range(self._worker_count)
        }

    def start(self) -> None:
        with self._state_lock:
            if self._threads:
                return
            self._stop_event.clear()
            for worker_id in range(self._worker_count):
                thread = threading.Thread(
                    target=self._run_worker,
                    args=(worker_id,),
                    name=f"optimizer-worker-{worker_id}",
                    daemon=True,
                )
                self._threads.append(thread)
                thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._scheduler.shutdown()
        for thread in list(self._threads):
            thread.join(timeout=2.0)
        with self._state_lock:
            for worker_id, snapshot in self._states.items():
                self._states[worker_id] = replace(snapshot, state=WorkerState.STOPPED)
            self._threads.clear()

    def snapshots(self) -> list[WorkerSnapshot]:
        with self._state_lock:
            return list(self._states.values())

    def _run_worker(self, worker_id: int) -> None:
        while not self._stop_event.is_set():
            self._set_worker(worker_id, WorkerState.WAITING, None, None)
            job = self._scheduler.acquire(timeout=0.25)
            if job is None:
                continue
            started = time.monotonic()
            self._set_worker(worker_id, WorkerState.RUNNING, job.job_id, str(job.file_path))
            error: str | None = None
            try:
                self._process_job(job)
            except OSError as exc:
                error = str(exc)
                self._logger.warning("Hashing failed for %s: %s", job.file_path, exc)
                self._metrics.file_failed()
            except Exception as exc:  # defensive worker containment
                error = f"{type(exc).__name__}: {exc}"
                self._logger.exception("Unexpected worker failure for %s", job.file_path)
                self._metrics.file_failed()
            finally:
                busy = time.monotonic() - started
                self._increment_worker(worker_id, busy, error is not None)
                self._scheduler.complete(job, error)
                self._metrics.file_processed()
                self._publisher.publish(
                    ScanEvent(
                        "job_completed",
                        {
                            "job_id": job.job_id,
                            "path": str(job.file_path),
                            "error": error,
                            "worker_id": worker_id,
                        },
                    )
                )

    def _process_job(self, job: ScanJob) -> None:
        original = self._record_from_job(job)
        partial = self._hasher.partial_hash(job.file_path)
        partial_record = self._duplicate_index.with_partial(original, partial)
        candidates = self._duplicate_index.accept_partial_hash(partial_record)
        for candidate in candidates:
            full_hash = self._hasher.full_hash(candidate.path)
            full_record = self._duplicate_index.with_full(candidate, full_hash)
            changed_groups = self._duplicate_index.accept_full_hash(full_record)
            if changed_groups:
                self._on_group_changed()
                for group in changed_groups:
                    self._publisher.publish(
                        ScanEvent(
                            "duplicate_group_updated",
                            {
                                "group_id": group.group_id,
                                "files": [str(item.path) for item in group.files],
                                "risk_score": group.risk_score,
                                "reclaimable_bytes": group.reclaimable_bytes,
                            },
                        )
                    )

    @staticmethod
    def _record_from_job(job: ScanJob):
        from smart_optimizer.domain.models import FileRecord

        return FileRecord(
            path=job.file_path,
            size_bytes=job.size_bytes,
            modified_at=job.modified_at,
            extension=job.extension,
            is_hidden=job.is_hidden,
            is_system=job.is_system,
        )

    def _set_worker(
        self,
        worker_id: int,
        state: WorkerState,
        job_id: str | None,
        current_file: str | None,
    ) -> None:
        with self._state_lock:
            current = self._states[worker_id]
            self._states[worker_id] = replace(
                current,
                state=state,
                current_job_id=job_id,
                current_file=current_file,
            )
            self._publish_workers_locked()

    def _increment_worker(self, worker_id: int, busy_seconds: float, failed: bool) -> None:
        with self._state_lock:
            current = self._states[worker_id]
            self._states[worker_id] = replace(
                current,
                processed_count=current.processed_count + 1,
                failed_count=current.failed_count + (1 if failed else 0),
                busy_seconds=current.busy_seconds + busy_seconds,
            )
            running = sum(1 for state in self._states.values() if state.state == WorkerState.RUNNING)
            self._metrics.set_thread_utilization(running / max(1, self._worker_count))
            self._publish_workers_locked()

    def _publish_workers_locked(self) -> None:
        self._publisher.publish(
            ScanEvent(
                "workers_updated",
                {"workers": [asdict(snapshot) for snapshot in self._states.values()]},
            )
        )
