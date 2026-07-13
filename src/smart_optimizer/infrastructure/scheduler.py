from __future__ import annotations

import heapq
import itertools
import threading
import time
from dataclasses import dataclass

from smart_optimizer.domain.models import JobState, ScanJob, SchedulerSnapshot


@dataclass(order=True, slots=True)
class _ScheduledItem:
    priority: int
    arrival_time: float
    sequence: int
    job: ScanJob


class AgingPriorityScheduler:
    """
    Condition-variable backed preemptive priority scheduler.

    The class name is retained for application compatibility, but dispatch is
    intentionally strict: min priority value first, FCFS for equal priorities.
    """

    def __init__(self, aging_threshold_seconds: float = 3.0, boost_amount: int = 1) -> None:
        self._condition = threading.Condition(threading.Lock())
        self._queue: list[_ScheduledItem] = []
        self._sequence = itertools.count()
        self._shutdown = False
        self._running = 0
        self._completed = 0
        self._failed = 0
        self._wait_times: list[float] = []

    def submit(self, job: ScanJob) -> None:
        with self._condition:
            if self._shutdown:
                return
            job.state = JobState.QUEUED
            arrival_time = time.monotonic()
            heapq.heappush(
                self._queue,
                _ScheduledItem(
                    priority=job.base_priority,
                    arrival_time=arrival_time,
                    sequence=next(self._sequence),
                    job=job,
                ),
            )
            self._condition.notify()

    def acquire(self, timeout: float) -> ScanJob | None:
        with self._condition:
            available = self._condition.wait_for(
                lambda: self._shutdown or bool(self._queue),
                timeout=timeout,
            )
            if not available or self._shutdown:
                return None
            item = heapq.heappop(self._queue)
            job = item.job
            job.effective_priority = item.priority
            job.state = JobState.READY
            waited = max(time.monotonic() - item.arrival_time, 0.0)
            self._wait_times.append(waited)
            self._running += 1
            job.state = JobState.RUNNING
            return job

    def complete(self, job: ScanJob, error: str | None = None) -> None:
        with self._condition:
            self._running = max(0, self._running - 1)
            if error is None:
                job.state = JobState.COMPLETED
                self._completed += 1
            else:
                job.state = JobState.FAILED
                job.error = error
                self._failed += 1

    def snapshot(self) -> SchedulerSnapshot:
        with self._condition:
            queued = len(self._queue)
            waits_ms = [wait * 1000.0 for wait in self._wait_times[-500:]]
            average_wait = sum(waits_ms) / len(waits_ms) if waits_ms else 0.0
            now = time.monotonic()
            oldest_wait = (
                max((now - item.arrival_time for item in self._queue), default=0.0) * 1000.0
            )
            return SchedulerSnapshot(
                queued=queued,
                ready=queued,
                running=self._running,
                completed=self._completed,
                failed=self._failed,
                average_wait_ms=average_wait,
                boosted_jobs=0,
                oldest_wait_ms=oldest_wait,
            )

    def shutdown(self) -> None:
        with self._condition:
            self._shutdown = True
            self._condition.notify_all()

