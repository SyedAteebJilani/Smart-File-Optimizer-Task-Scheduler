from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from smart_optimizer.domain.models import (
    DuplicateGroup,
    FileRecord,
    RiskLevel,
    ScanRequest,
    ScanSummary,
)


class SQLiteConnectionFactory:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path, timeout=30.0, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def execute_locked(self, action):
        with self._lock:
            with closing(self.connect()) as connection:
                with connection:
                    return action(connection)

    def _initialize(self) -> None:
        with closing(self.connect()) as connection:
            with connection:
                connection.executescript(
                    """
                CREATE TABLE IF NOT EXISTS scan_history (
                    scan_id TEXT PRIMARY KEY,
                    root_path TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    files_discovered INTEGER NOT NULL DEFAULT 0,
                    files_processed INTEGER NOT NULL DEFAULT 0,
                    duplicate_groups INTEGER NOT NULL DEFAULT 0,
                    reclaimable_bytes INTEGER NOT NULL DEFAULT 0,
                    errors INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS duplicate_groups (
                    scan_id TEXT NOT NULL,
                    group_id TEXT NOT NULL,
                    full_hash TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    risk_score INTEGER NOT NULL,
                    risk_level TEXT NOT NULL,
                    reclaimable_bytes INTEGER NOT NULL,
                    files_json TEXT NOT NULL,
                    PRIMARY KEY (scan_id, group_id),
                    FOREIGN KEY (scan_id) REFERENCES scan_history(scan_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS duplicate_folder_learning (
                    folder_path TEXT PRIMARY KEY,
                    duplicate_count INTEGER NOT NULL DEFAULT 0,
                    last_seen TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ignored_directories (
                    folder_path TEXT PRIMARY KEY,
                    reason TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS deletion_metadata (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    risk_score INTEGER NOT NULL,
                    deleted_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analytics (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
                )


class SQLiteScanHistoryRepository:
    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        self._factory = factory

    def create_scan(self, request: ScanRequest) -> str:
        def action(connection: sqlite3.Connection) -> str:
            connection.execute(
                """
                INSERT OR REPLACE INTO scan_history
                (scan_id, root_path, started_at, files_discovered, files_processed,
                 duplicate_groups, reclaimable_bytes, errors)
                VALUES (?, ?, ?, 0, 0, 0, 0, 0)
                """,
                (
                    request.request_id,
                    str(request.root_path),
                    request.created_at.isoformat(),
                ),
            )
            return request.request_id

        return self._factory.execute_locked(action)

    def finish_scan(self, summary: ScanSummary) -> None:
        def action(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                UPDATE scan_history
                SET finished_at = ?, files_discovered = ?, files_processed = ?,
                    duplicate_groups = ?, reclaimable_bytes = ?, errors = ?
                WHERE scan_id = ?
                """,
                (
                    _dt(summary.finished_at),
                    summary.files_discovered,
                    summary.files_processed,
                    summary.duplicate_groups,
                    summary.reclaimable_bytes,
                    summary.errors,
                    summary.scan_id,
                ),
            )

        self._factory.execute_locked(action)

    def list_recent_scans(self, limit: int) -> list[ScanSummary]:
        def action(connection: sqlite3.Connection) -> list[ScanSummary]:
            rows = connection.execute(
                """
                SELECT * FROM scan_history
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [_summary_from_row(row) for row in rows]

        return self._factory.execute_locked(action)


class SQLiteDuplicateRepository:
    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        self._factory = factory

    def replace_groups(self, scan_id: str, groups: list[DuplicateGroup]) -> None:
        def action(connection: sqlite3.Connection) -> None:
            connection.execute("DELETE FROM duplicate_groups WHERE scan_id = ?", (scan_id,))
            connection.executemany(
                """
                INSERT INTO duplicate_groups
                (scan_id, group_id, full_hash, size_bytes, risk_score, risk_level,
                 reclaimable_bytes, files_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        scan_id,
                        group.group_id,
                        group.full_hash,
                        group.size_bytes,
                        group.risk_score,
                        group.risk_level.value,
                        group.reclaimable_bytes,
                        json.dumps([_file_to_json(file) for file in group.files]),
                    )
                    for group in groups
                ],
            )

        self._factory.execute_locked(action)

    def load_groups(self, scan_id: str) -> list[DuplicateGroup]:
        def action(connection: sqlite3.Connection) -> list[DuplicateGroup]:
            rows = connection.execute(
                "SELECT * FROM duplicate_groups WHERE scan_id = ? ORDER BY risk_score DESC",
                (scan_id,),
            ).fetchall()
            return [_group_from_row(row) for row in rows]

        return self._factory.execute_locked(action)


class SQLiteLearningRepository:
    def __init__(self, factory: SQLiteConnectionFactory) -> None:
        self._factory = factory

    def record_duplicate_group(self, group: DuplicateGroup) -> None:
        now = datetime.now(timezone.utc).isoformat()

        def action(connection: sqlite3.Connection) -> None:
            for file in group.files:
                folder = str(file.path.parent)
                connection.execute(
                    """
                    INSERT INTO duplicate_folder_learning(folder_path, duplicate_count, last_seen)
                    VALUES (?, 1, ?)
                    ON CONFLICT(folder_path) DO UPDATE SET
                        duplicate_count = duplicate_count + 1,
                        last_seen = excluded.last_seen
                    """,
                    (folder, now),
                )

        self._factory.execute_locked(action)

    def record_deletion(self, path: Path, size_bytes: int, risk_score: int) -> None:
        now = datetime.now(timezone.utc).isoformat()

        def action(connection: sqlite3.Connection) -> None:
            connection.execute(
                """
                INSERT INTO deletion_metadata(path, extension, size_bytes, risk_score, deleted_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(path), path.suffix.lower(), size_bytes, risk_score, now),
            )

        self._factory.execute_locked(action)

    def ignored_directories(self) -> set[Path]:
        def action(connection: sqlite3.Connection) -> set[Path]:
            rows = connection.execute("SELECT folder_path FROM ignored_directories").fetchall()
            return {Path(str(row["folder_path"])) for row in rows}

        return self._factory.execute_locked(action)

    def folder_duplicate_counts(self) -> dict[Path, int]:
        def action(connection: sqlite3.Connection) -> dict[Path, int]:
            rows = connection.execute(
                "SELECT folder_path, duplicate_count FROM duplicate_folder_learning"
            ).fetchall()
            return {Path(str(row["folder_path"])): int(row["duplicate_count"]) for row in rows}

        return self._factory.execute_locked(action)

    def deletion_patterns(self) -> dict[str, int]:
        def action(connection: sqlite3.Connection) -> dict[str, int]:
            rows = connection.execute(
                "SELECT extension, COUNT(*) AS count FROM deletion_metadata GROUP BY extension"
            ).fetchall()
            return {str(row["extension"]): int(row["count"]) for row in rows}

        return self._factory.execute_locked(action)


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value)


def _summary_from_row(row: sqlite3.Row) -> ScanSummary:
    return ScanSummary(
        scan_id=str(row["scan_id"]),
        root_path=Path(str(row["root_path"])),
        started_at=datetime.fromisoformat(str(row["started_at"])),
        finished_at=_parse_dt(row["finished_at"]),
        files_discovered=int(row["files_discovered"]),
        files_processed=int(row["files_processed"]),
        duplicate_groups=int(row["duplicate_groups"]),
        reclaimable_bytes=int(row["reclaimable_bytes"]),
        errors=int(row["errors"]),
    )


def _file_to_json(record: FileRecord) -> dict[str, object]:
    return {
        "path": str(record.path),
        "size_bytes": record.size_bytes,
        "modified_at": record.modified_at,
        "extension": record.extension,
        "is_hidden": record.is_hidden,
        "is_system": record.is_system,
        "partial_hash": record.partial_hash,
        "full_hash": record.full_hash,
        "error": record.error,
    }


def _file_from_json(data: dict[str, object]) -> FileRecord:
    return FileRecord(
        path=Path(str(data["path"])),
        size_bytes=int(data["size_bytes"]),
        modified_at=float(data["modified_at"]),
        extension=str(data["extension"]),
        is_hidden=bool(data["is_hidden"]),
        is_system=bool(data["is_system"]),
        partial_hash=str(data["partial_hash"]) if data.get("partial_hash") else None,
        full_hash=str(data["full_hash"]) if data.get("full_hash") else None,
        error=str(data["error"]) if data.get("error") else None,
    )


def _group_from_row(row: sqlite3.Row) -> DuplicateGroup:
    files_data = json.loads(str(row["files_json"]))
    files = tuple(_file_from_json(item) for item in files_data)
    return DuplicateGroup(
        group_id=str(row["group_id"]),
        full_hash=str(row["full_hash"]),
        size_bytes=int(row["size_bytes"]),
        files=files,
        risk_score=int(row["risk_score"]),
        risk_level=RiskLevel(str(row["risk_level"])),
        reclaimable_bytes=int(row["reclaimable_bytes"]),
    )
