"""
presentation/main_window.py
============================
Main application shell for the Smart File Cleaner dashboard.

Audit log (2026-06-03):
  FIX-A  _on_scan_finished / _on_error — dialog is assigned to a local
          variable before .exec() so Qt keeps the Python object alive for the
          duration of the modal loop.  reclaimable_bytes is extracted with the
          _as_number helper to survive None / non-numeric payloads.
  FIX-B  _start_scan — validates that the path is not empty before calling
          the controller; shows a toast error instead of passing "" down.
  FIX-C  _apply_theme — moved after _graph_views is initialised; early call
          from __init__ no longer risks AttributeError.
  FIX-D  _build_sidebar lambda — simplified; only captures what it needs.
  FIX-E  resizeEvent — ToastManager._layout_toasts now exposes a public API;
          guard kept as a safety net for edge cases during construction.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QScroller,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from smart_optimizer.application.controller import ScanController
from smart_optimizer.application.events import QtEventBridge
from smart_optimizer.presentation.theme import DARK_STYLE, LIGHT_STYLE
from smart_optimizer.presentation.widgets import (
    AnalyticsPanel,
    DuplicateTable,
    ExecutionTimeline,
    LiveGraphs,
    MetricsDashboard,
    PremiumMessageDialog,
    SchedulerPanel,
    SettingsPanel,
    StatusPill,
    ToastManager,
    WorkerPanel,
    _as_number,
    format_bytes,
)


class MainWindow(QMainWindow):
    def __init__(self, controller: ScanController, events: QtEventBridge) -> None:
        super().__init__()
        self._controller = controller
        self._events = events
        self._dark = True
        self._nav_buttons: list[QPushButton] = []

        self.setWindowTitle("Smart File Cleaner")
        self.resize(1480, 920)
        self.setMinimumSize(1180, 760)

        # Build UI first so all widget references exist before we wire signals
        # or call _apply_theme (FIX-C).
        self._build_ui()
        self._connect_events()

        # ToastManager must be created after setCentralWidget so parent
        # geometry is valid for positioning.
        self._toast = ToastManager(self)

        # Apply theme last — all graph views exist at this point (FIX-C).
        self._apply_theme()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        shell = QHBoxLayout(root)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._build_sidebar())
        shell.addWidget(self._build_content(), 1)
        self.setCentralWidget(root)

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(254)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(10)

        brand = QLabel("Smart File Cleaner")
        brand.setObjectName("BrandTitle")
        subtitle = QLabel("Find duplicate junk safely")
        subtitle.setObjectName("BrandSubtitle")
        layout.addWidget(brand)
        layout.addWidget(subtitle)
        layout.addSpacing(18)

        # FIX-D: explicit default-argument capture; 'short' removed (unused).
        pages = [
            "Home Dashboard",
            "Current Scan",
            "Work Planner",
            "Duplicate Finder",
            "Insights",
            "Settings",
        ]
        for index, label in enumerate(pages):
            button = QPushButton(label)
            button.setObjectName("NavButton")
            button.setProperty("active", "true" if index == 0 else "false")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(
                lambda _checked=False, p=index, t=label: self._select_page(p, t)
            )
            self._nav_buttons.append(button)
            layout.addWidget(button)

        layout.addStretch(1)
        self._sidebar_status = StatusPill("Idle", "#9fb0c8")
        layout.addWidget(QLabel("App Status"))
        layout.addWidget(self._sidebar_status)
        return sidebar

    def _build_content(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 20, 22, 22)
        layout.setSpacing(16)

        self._page_title = QLabel("Home Dashboard")
        self._page_title.setObjectName("PageTitle")
        self._page_subtitle = QLabel(
            "See what is being scanned, what is waiting, and what can be cleaned."
        )
        self._page_subtitle.setObjectName("SectionSubtitle")
        title_row = QVBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(3)
        title_row.addWidget(self._page_title)
        title_row.addWidget(self._page_subtitle)
        layout.addLayout(title_row)

        layout.addWidget(self._build_scan_bar())

        # Instantiate all panels.
        self._overview_metrics = MetricsDashboard()
        self._scan_metrics = MetricsDashboard()
        self._scheduler = SchedulerPanel()
        self._workers_panel = WorkerPanel()
        self._timeline = ExecutionTimeline()
        self._overview_graphs = LiveGraphs()
        self._scheduler_graphs = LiveGraphs()
        self._analytics_graphs = LiveGraphs()
        self._duplicates = DuplicateTable()
        self._duplicates.set_delete_handler(self._delete_duplicate_file)
        self._analytics = AnalyticsPanel()
        self._settings = SettingsPanel()

        self._metric_views = [self._overview_metrics, self._scan_metrics]
        self._graph_views = [
            self._overview_graphs,
            self._scheduler_graphs,
            self._analytics_graphs,
        ]

        self._stack = QStackedWidget()
        self._stack.addWidget(self._scroll_page(self._overview_page()))
        self._stack.addWidget(self._scroll_page(self._active_scans_page()))
        self._stack.addWidget(self._scroll_page(self._scheduler_page()))
        self._stack.addWidget(self._scroll_page(self._duplicates_page()))
        self._stack.addWidget(self._scroll_page(self._analytics_page()))
        self._stack.addWidget(self._scroll_page(self._settings_page()))
        layout.addWidget(self._stack, 1)
        return content

    def _build_scan_bar(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("HeroPanel")
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QGridLayout(panel)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(10)

        self._path = QLineEdit()
        self._path.setPlaceholderText("Choose a directory to scan")

        browse = QPushButton("Browse")
        browse.setObjectName("SecondaryButton")
        browse.clicked.connect(self._browse)

        self._include_hidden = QCheckBox("Include hidden files")

        self._workers = QSpinBox()
        self._workers.setRange(1, 6)
        self._workers.setValue(3)
        self._workers.setToolTip("Number of scanning robots (1–6)")

        self._start = QPushButton("Start Scan")
        self._stop = QPushButton("Stop")
        self._stop.setObjectName("DangerButton")
        self._stop.setEnabled(False)

        self._theme = QToolButton()
        self._theme.setObjectName("SecondaryButton")
        self._theme.setText("Light")
        self._theme.setToolTip("Toggle dark or light mode")

        self._status = QLabel("Ready")
        self._status.setObjectName("MutedText")

        self._start.clicked.connect(self._start_scan)
        self._stop.clicked.connect(self._stop_scan)
        self._theme.clicked.connect(self._toggle_theme)

        layout.addWidget(QLabel("Folder to scan"), 0, 0)
        layout.addWidget(self._path, 0, 1, 1, 4)
        layout.addWidget(browse, 0, 5)
        layout.addWidget(QLabel("Robots"), 1, 0)
        layout.addWidget(self._workers, 1, 1)
        layout.addWidget(self._include_hidden, 1, 2)
        layout.addWidget(self._status, 1, 3)
        layout.addWidget(self._start, 1, 4)
        layout.addWidget(self._stop, 1, 5)
        layout.addWidget(self._theme, 1, 6)
        layout.setColumnStretch(4, 1)
        return panel

    # ------------------------------------------------------------------
    # Page builders
    # ------------------------------------------------------------------

    def _overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self._overview_metrics)
        layout.addWidget(self._overview_graphs)
        return page

    def _active_scans_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self._workers_panel)
        layout.addWidget(self._scan_metrics)
        return page

    def _scheduler_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self._timeline)
        layout.addWidget(self._scheduler)
        layout.addWidget(self._scheduler_graphs)
        return page

    def _duplicates_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._duplicates)
        return page

    def _analytics_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self._analytics)
        layout.addWidget(self._analytics_graphs)
        return page

    def _settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        layout.addWidget(self._settings)
        layout.addStretch(1)
        return page

    def _scroll_page(self, widget: QWidget) -> QScrollArea:
        """Wrap *widget* in a scroll area with kinetic / buttery-smooth
        scrolling enabled.  Every page in the stack goes through this so
        mouse-wheel and touch-pad flinging feels natural everywhere.
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(widget)
        # Kinetic scrolling — left-mouse drag gives momentum.
        QScroller.grabGesture(
            scroll.viewport(),
            QScroller.ScrollerGestureType.LeftMouseButtonGesture,
        )
        scroll.verticalScrollBar().setSingleStep(20)
        return scroll

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_events(self) -> None:
        self._events.scan_started.connect(self._on_scan_started)
        self._events.scan_finished.connect(self._on_scan_finished)
        self._events.metrics_updated.connect(self._on_metrics)
        self._events.scheduler_updated.connect(self._scheduler.update_scheduler)
        self._events.workers_updated.connect(self._workers_panel.update_workers)
        self._events.job_completed.connect(self._timeline.add_job)
        self._events.duplicates_updated.connect(self._duplicates.update_groups)
        self._events.file_deleted.connect(self._on_file_deleted)
        self._events.error_reported.connect(self._on_error)
        # Settings panel toggles — previously disconnected (FIX-SETTINGS).
        self._settings.theme_changed.connect(self._set_dark_mode)
        self._settings.include_hidden_changed.connect(self._set_include_hidden)

    # ------------------------------------------------------------------
    # User actions
    # ------------------------------------------------------------------

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Select scan directory")
        if directory:
            self._path.setText(directory)

    def _start_scan(self) -> None:
        # FIX-B: validate path before calling the controller.
        path = self._path.text().strip()
        if not path:
            self._toast.show(
                "Please choose a folder to scan before starting.", "warning"
            )
            return
        self._controller.start_scan(
            path,
            self._include_hidden.isChecked(),
            self._workers.value(),
        )

    def _stop_scan(self) -> None:
        self._controller.stop_scan()
        self._status.setText("Stopping scan…")
        self._sidebar_status.setText("Stopping")
        self._sidebar_status.set_color("#f2c76e")
        self._toast.show("Scan stop requested.", "warning")

    def _toggle_theme(self) -> None:
        """Called by the toolbar theme button — toggles dark/light."""
        self._dark = not self._dark
        self._apply_theme()

    def _set_dark_mode(self, enabled: bool) -> None:
        """Slot connected to SettingsPanel.theme_changed.

        Keeps self._dark in sync with the Settings toggle and propagates the
        change to the stylesheet and all live graphs.  Also mirrors the state
        back to the Settings panel's toggle so the UI stays consistent if the
        toggle was programmatically changed from elsewhere.
        """
        if self._dark == enabled:
            return  # No-op: already in the requested state.
        self._dark = enabled
        self._apply_theme()
        # Mirror to the settings panel so the toggle reflects reality.
        self._settings.set_dark_mode(enabled)

    def _set_include_hidden(self, enabled: bool) -> None:
        """Slot connected to SettingsPanel.include_hidden_changed.

        Syncs the scan-bar checkbox with the Settings toggle so both controls
        always agree and the next scan picks up the correct value.
        """
        self._include_hidden.setChecked(enabled)

    def _apply_theme(self) -> None:
        self.setStyleSheet(DARK_STYLE if self._dark else LIGHT_STYLE)
        self._theme.setText("Light" if self._dark else "Dark")
        for graph in self._graph_views:
            graph.apply_theme(self._dark)

    def _select_page(self, index: int, title: str) -> None:
        subtitles = {
            0: "See what is being scanned, what is waiting, and what can be cleaned.",
            1: "Watch the scanning robots check files in the background.",
            2: "See the order files are checked and which robot handled them.",
            3: "Review files that are exactly the same on the inside.",
            4: "Understand scan progress and clean-up potential in plain English.",
            5: "Choose scan options and appearance.",
        }
        self._stack.setCurrentIndex(index)
        self._page_title.setText(title)
        self._page_subtitle.setText(subtitles.get(index, ""))
        for btn_index, button in enumerate(self._nav_buttons):
            button.setProperty("active", "true" if btn_index == index else "false")
            button.style().unpolish(button)
            button.style().polish(button)

    # ------------------------------------------------------------------
    # Event handlers (connected to QtEventBridge signals)
    # ------------------------------------------------------------------

    def _on_scan_started(self, payload: dict[str, object]) -> None:
        self._start.setEnabled(False)
        self._stop.setEnabled(True)
        self._timeline.reset()
        root = str(payload.get("root_path", ""))
        self._status.setText(f"Scanning {root}")
        self._sidebar_status.setText("Scanning")
        self._sidebar_status.set_color("#5dd6b5")
        self._toast.show("Scan started.", "success")

    def _on_scan_finished(self, payload: dict[str, object]) -> None:
        self._start.setEnabled(True)
        self._stop.setEnabled(False)

        discovered = int(_as_number(payload, "files_discovered"))
        groups = int(_as_number(payload, "duplicate_groups"))
        # FIX-A: use _as_number so None / bad values don't raise TypeError.
        junk_space = _as_number(payload, "reclaimable_bytes")

        self._status.setText(
            f"Done: {discovered:,} files found, {groups:,} duplicate groups"
        )
        self._sidebar_status.setText("Complete")
        self._sidebar_status.set_color("#7aa7ff")
        self._toast.show(f"Scan complete: {discovered:,} files checked.", "success")
        self._toast.show(f"Duplicate review ready: {groups:,} groups found.", "info")

        # FIX-A: assign to local variable so Qt owns the object lifetime for
        # the entire duration of the blocking exec() call.
        dialog = PremiumMessageDialog(
            "Scan Successfully Completed",
            (
                f"We checked {discovered:,} files and found {groups:,} duplicate groups. "
                "Nothing has been removed yet, so you can review everything safely first."
            ),
            f"{format_bytes(junk_space)} junk space found",
            "success",
            self,
        )
        dialog.exec()

    def _on_metrics(self, payload: dict[str, object]) -> None:
        for metrics in self._metric_views:
            metrics.update_metrics(payload)
        for graph in self._graph_views:
            graph.update_metrics(payload)
        self._analytics.update_metrics(payload)

    def _on_error(self, payload: dict[str, object]) -> None:
        message = str(payload.get("message", "Unknown error"))
        self._start.setEnabled(True)
        self._stop.setEnabled(False)
        self._status.setText(message)
        self._sidebar_status.setText("Attention")
        self._sidebar_status.set_color("#ff7a8a")
        self._toast.show(message, "error")

        # FIX-A: local variable keeps Python object alive through exec().
        dialog = PremiumMessageDialog(
            "Oops! We couldn't read a folder",
            (
                "The scan could not continue because Windows blocked access to a file "
                "or folder, or the selected folder is no longer available.\n\n"
                f"Details: {message}"
            ),
            None,
            "error",
            self,
        )
        dialog.exec()

    def _delete_duplicate_file(
        self,
        path: str,
        size_bytes: int,
        risk_score: int,
    ) -> tuple[bool, str]:
        success, message = self._controller.delete_duplicate_file(
            path, size_bytes, risk_score
        )
        if not success:
            self._toast.show(message, "error")
        return success, message

    def _on_file_deleted(self, payload: dict[str, object]) -> None:
        path = str(payload.get("path", ""))
        display = path.rsplit("\\", 1)[-1] if "\\" in path else path.rsplit("/", 1)[-1]
        self._toast.show(f"Removed duplicate: {display}", "success")

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        # FIX-E: guard is a safety net for the window resize that fires
        # during construction before _toast is assigned.
        if hasattr(self, "_toast"):
            self._toast._layout_toasts()
