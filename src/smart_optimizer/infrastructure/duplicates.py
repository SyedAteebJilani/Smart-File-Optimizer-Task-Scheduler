from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import replace
from uuid import uuid4

from smart_optimizer.domain.models import DuplicateGroup, FileRecord
from smart_optimizer.domain.risk import RiskScoringEngine


class ThreadSafeDuplicateIndex:
    def __init__(self, risk_engine: RiskScoringEngine) -> None:
        self._risk_engine = risk_engine
        self._mutex = threading.Lock()
        self._size_index: dict[int, list[FileRecord]] = defaultdict(list)
        self._partial_index: dict[tuple[int, str], list[FileRecord]] = defaultdict(list)
        self._full_index: dict[str, list[FileRecord]] = defaultdict(list)
        self._groups: dict[str, DuplicateGroup] = {}

    def reset(self) -> None:
        with self._mutex:
            self._size_index.clear()
            self._partial_index.clear()
            self._full_index.clear()
            self._groups.clear()

    def register_file(self, record: FileRecord) -> list[FileRecord]:
        if record.size_bytes <= 0:
            return []

        with self._mutex:
            bucket = self._size_index[record.size_bytes]
            bucket.append(record)
            bucket_size = len(bucket)
            if bucket_size == 2:
                return list(bucket)
            if bucket_size > 2:
                return [record]
            return []

    def accept_partial_hash(self, record: FileRecord) -> list[FileRecord]:
        if record.partial_hash is None:
            return []

        key = (record.size_bytes, record.partial_hash)
        with self._mutex:
            bucket = self._partial_index[key]
            if any(existing.path == record.path for existing in bucket):
                return []
            bucket.append(record)
            bucket_size = len(bucket)
            if bucket_size == 2:
                return list(bucket)
            if bucket_size > 2:
                return [record]
            return []

    def accept_full_hash(self, record: FileRecord) -> list[DuplicateGroup]:
        if record.full_hash is None or not self._is_sha256_hexdigest(record.full_hash):
            return []

        full_hash = record.full_hash
        with self._mutex:
            bucket = self._full_index[full_hash]
            for index, existing in enumerate(bucket):
                if existing.path == record.path:
                    bucket[index] = record
                    break
            else:
                bucket.append(record)
            files_snapshot = tuple(bucket)
            existing_group = self._groups.get(full_hash)
            group_id = existing_group.group_id if existing_group is not None else str(uuid4())

        if len(files_snapshot) < 2:
            return []

        risk_score, risk_level = self._risk_engine.score_group(files_snapshot)
        reclaimable = max(0, (len(files_snapshot) - 1) * record.size_bytes)
        group = DuplicateGroup(
            group_id=group_id,
            full_hash=full_hash,
            size_bytes=record.size_bytes,
            files=files_snapshot,
            risk_score=risk_score,
            risk_level=risk_level,
            reclaimable_bytes=reclaimable,
        )

        with self._mutex:
            current_bucket = tuple(self._full_index.get(full_hash, ()))
            if len(current_bucket) != len(files_snapshot):
                return []
            self._groups[full_hash] = group

        return [group]

    def groups(self) -> list[DuplicateGroup]:
        with self._mutex:
            return list(self._groups.values())

    @staticmethod
    def with_partial(record: FileRecord, partial_hash: str) -> FileRecord:
        return replace(record, partial_hash=partial_hash)

    @staticmethod
    def with_full(record: FileRecord, full_hash: str) -> FileRecord:
        return replace(record, full_hash=full_hash)

    @staticmethod
    def with_error(record: FileRecord, error: str) -> FileRecord:
        return replace(record, error=error)

    @staticmethod
    def _is_sha256_hexdigest(value: str) -> bool:
        if len(value) != 64:
            return False
        return all(char in "0123456789abcdefABCDEF" for char in value)

