from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox

from smart_optimizer.application.bootstrap import build_application
from smart_optimizer.presentation.main_window import MainWindow


def main() -> int:
    if os.name != "nt":
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Unsupported platform",
            "Smart File Optimizer is a Windows-only demonstration application.",
        )
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName("Smart File Optimizer")
    app.setOrganizationName("OS Demonstration Lab")

    data_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SmartFileOptimizer"
    services = build_application(data_dir)
    window = MainWindow(services.controller, services.event_bridge)
    window.show()

    exit_code = app.exec()
    services.controller.shutdown()
    return int(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())

