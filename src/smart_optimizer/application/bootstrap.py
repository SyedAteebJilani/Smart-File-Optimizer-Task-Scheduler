from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from smart_optimizer.application.controller import ScanController
from smart_optimizer.application.events import QtEventBridge
from smart_optimizer.domain.risk import RiskScoringEngine
from smart_optimizer.infrastructure.database import (
    SQLiteConnectionFactory,
    SQLiteDuplicateRepository,
    SQLiteLearningRepository,
    SQLiteScanHistoryRepository,
)
from smart_optimizer.infrastructure.duplicates import ThreadSafeDuplicateIndex
from smart_optimizer.infrastructure.filesystem import WindowsFileSystemScanner
from smart_optimizer.infrastructure.hashing import Sha256FileHasher
from smart_optimizer.infrastructure.logging_config import configure_logging
from smart_optimizer.infrastructure.metrics import MetricsTracker


@dataclass(frozen=True, slots=True)
class ApplicationServices:
    controller: ScanController
    event_bridge: QtEventBridge


def build_application(data_dir: Path) -> ApplicationServices:
    logger = configure_logging(data_dir)
    database = SQLiteConnectionFactory(data_dir / "smart_optimizer.db")
    event_bridge = QtEventBridge()
    metrics = MetricsTracker()
    duplicate_index = ThreadSafeDuplicateIndex(RiskScoringEngine())
    controller = ScanController(
        scanner=WindowsFileSystemScanner(logger),
        duplicate_index=duplicate_index,
        hasher=Sha256FileHasher(),
        history_repository=SQLiteScanHistoryRepository(database),
        duplicate_repository=SQLiteDuplicateRepository(database),
        learning_repository=SQLiteLearningRepository(database),
        metrics=metrics,
        event_bridge=event_bridge,
        logger=logger,
    )
    return ApplicationServices(controller=controller, event_bridge=event_bridge)

