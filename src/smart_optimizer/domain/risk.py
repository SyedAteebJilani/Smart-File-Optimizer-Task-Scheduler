from __future__ import annotations

import time
from pathlib import Path

from smart_optimizer.domain.models import FileRecord, RiskLevel


class RiskScoringEngine:
    _sensitive_extensions = {
        ".dll",
        ".sys",
        ".exe",
        ".bat",
        ".ps1",
        ".reg",
        ".ini",
        ".db",
        ".sqlite",
        ".key",
        ".pem",
        ".pfx",
        ".crt",
    }

    _system_markers = (
        "\\windows\\",
        "\\program files\\",
        "\\program files (x86)\\",
        "\\programdata\\",
        "\\appdata\\local\\microsoft\\",
        "\\appdata\\roaming\\microsoft\\",
    )

    def score_group(self, files: tuple[FileRecord, ...]) -> tuple[int, RiskLevel]:
        score = 0
        now = time.time()
        for record in files:
            normalized = str(record.path).lower()
            if any(marker in normalized for marker in self._system_markers):
                score += 30
            if record.extension.lower() in self._sensitive_extensions:
                score += 25
            if record.is_hidden:
                score += 10
            if record.is_system:
                score += 20
            age_days = max((now - record.modified_at) / 86_400.0, 0.0)
            if age_days < 7:
                score += 15
            elif age_days < 30:
                score += 8

        normalized_score = min(100, score)
        if normalized_score >= 80:
            return normalized_score, RiskLevel.CRITICAL
        if normalized_score >= 55:
            return normalized_score, RiskLevel.HIGH
        if normalized_score >= 25:
            return normalized_score, RiskLevel.MEDIUM
        return normalized_score, RiskLevel.LOW


def is_path_near_system_area(path: Path) -> bool:
    normalized = str(path).lower()
    return any(marker in normalized for marker in RiskScoringEngine._system_markers)

