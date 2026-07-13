from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path
from typing import Callable

from smart_optimizer.domain.models import FileRecord, ScanRequest, ScanSummary, utc_now


FILE_ATTRIBUTE_HIDDEN = 0x2
FILE_ATTRIBUTE_SYSTEM = 0x4

PROTECTED_PATH_MARKERS = (
    "\\windows\\",
    "\\program files\\",
    "\\program files (x86)\\",
    "\\programdata\\microsoft\\",
    "\\system volume information\\",
    "\\$recycle.bin\\",
    "\\recovery\\",
    "\\boot\\",
    "\\efi\\",
    "\\windows.old\\",
)

PROTECTED_FILE_NAMES = {
    "hiberfil.sys",
    "pagefile.sys",
    "swapfile.sys",
    "ntuser.dat",
    "ntuser.dat.log1",
    "ntuser.dat.log2",
    "usrclass.dat",
}

REGISTRY_HIVE_MARKERS = (
    "\\windows\\system32\\config\\sam",
    "\\windows\\system32\\config\\security",
    "\\windows\\system32\\config\\software",
    "\\windows\\system32\\config\\system",
    "\\windows\\system32\\config\\default",
)


class WindowsFileSystemScanner:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def scan(self, request: ScanRequest, on_file: Callable[[FileRecord], None]) -> ScanSummary:
        started_at = utc_now()
        discovered = 0
        errors = 0
        root = request.root_path
        if not root.exists() or not root.is_dir():
            return ScanSummary(
                scan_id=request.request_id,
                root_path=root,
                started_at=started_at,
                finished_at=utc_now(),
                files_discovered=0,
                files_processed=0,
                duplicate_groups=0,
                reclaimable_bytes=0,
                errors=1,
            )
        if self._is_excluded_path(root):
            self._logger.info("Skipping protected scan root: %s", root)
            return ScanSummary(
                scan_id=request.request_id,
                root_path=root,
                started_at=started_at,
                finished_at=utc_now(),
                files_discovered=0,
                files_processed=0,
                duplicate_groups=0,
                reclaimable_bytes=0,
                errors=0,
            )

        for current_root, dir_names, file_names in os.walk(root, topdown=True, onerror=None):
            current_path = Path(current_root)
            if self._is_excluded_path(current_path):
                dir_names.clear()
                continue
            self._filter_directories(current_path, dir_names, request.include_hidden)
            for file_name in file_names:
                path = current_path / file_name
                if self._is_excluded_path(path) or self._is_protected_file(path):
                    continue
                try:
                    record = self._record_for_path(path)
                    if not request.include_hidden and record.is_hidden:
                        continue
                    discovered += 1
                    on_file(record)
                except OSError as exc:
                    errors += 1
                    self._logger.warning("Unable to inspect file %s: %s", path, exc)

        return ScanSummary(
            scan_id=request.request_id,
            root_path=root,
            started_at=started_at,
            finished_at=utc_now(),
            files_discovered=discovered,
            files_processed=0,
            duplicate_groups=0,
            reclaimable_bytes=0,
            errors=errors,
        )

    def _filter_directories(
        self,
        current_path: Path,
        dir_names: list[str],
        include_hidden: bool,
    ) -> None:
        visible: list[str] = []
        for name in dir_names:
            directory_path = current_path / name
            if self._is_excluded_path(directory_path):
                continue
            if include_hidden:
                visible.append(name)
                continue
            try:
                attrs = self._attributes(directory_path)
                hidden = bool(attrs & FILE_ATTRIBUTE_HIDDEN) or name.startswith(".")
            except OSError:
                hidden = name.startswith(".")
            if not hidden:
                visible.append(name)
        dir_names[:] = visible

    def _record_for_path(self, path: Path) -> FileRecord:
        stat_result = path.stat()
        attrs = self._attributes(path)
        return FileRecord(
            path=path,
            size_bytes=int(stat_result.st_size),
            modified_at=float(stat_result.st_mtime),
            extension=path.suffix.lower(),
            is_hidden=bool(attrs & FILE_ATTRIBUTE_HIDDEN) or path.name.startswith("."),
            is_system=bool(attrs & FILE_ATTRIBUTE_SYSTEM),
        )

    @staticmethod
    def _attributes(path: Path) -> int:
        if os.name != "nt":
            return FILE_ATTRIBUTE_HIDDEN if path.name.startswith(".") else 0
        result = ctypes.windll.kernel32.GetFileAttributesW(str(path))  # type: ignore[attr-defined]
        if result == -1:
            return 0
        return int(result)

    @classmethod
    def _is_excluded_path(cls, path: Path) -> bool:
        normalized = cls._normalized_path(path)
        return any(marker in normalized for marker in PROTECTED_PATH_MARKERS) or any(
            marker in normalized for marker in REGISTRY_HIVE_MARKERS
        )

    @classmethod
    def _is_protected_file(cls, path: Path) -> bool:
        name = path.name.lower()
        if name in PROTECTED_FILE_NAMES:
            return True
        normalized = cls._normalized_path(path)
        return any(marker in normalized for marker in REGISTRY_HIVE_MARKERS)

    @staticmethod
    def _normalized_path(path: Path) -> str:
        text = str(path).replace("/", "\\").lower().strip("\\")
        return f"\\{text}\\"
