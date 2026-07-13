"""
presentation/widgets.py
=======================
All reusable PyQt6 widgets for the Smart File Cleaner dashboard.

Revision (2026-06-03) — Rapid7-style flat enterprise UI:
  - REMOVED HoverCard, HoverCardController, attach_hover_card (all hover
    tooltips gone — every site that called attach_hover_card is cleaned up).
  - REMOVED DoughnutChart (replaced by flat QProgressBar / spark lines).
  - MetricTile redesigned: giant centered BigNumber + uppercase TileLabel,
    no animation machinery.
  - MetricsDashboard rebuilt as a 3-row Rapid7 grid:
      Row 0  — EnterpriseSummaryBar  (full-width KPI strip)
      Row 1  — 4 × EnterpriseTile    (big number + optional spark line)
      Row 2  — 2 × EnterpriseStatBar (label + flat progress bar + value)
  - All glassmorphism styling removed; panels are flat with 0 px radius.
  - Toast / ToastManager, PremiumMessageDialog, DuplicateTable, WorkerPanel,
    SchedulerPanel, AnalyticsPanel, LiveGraphs, ExecutionTimeline, and
    SettingsPanel are all preserved and cleaned up.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Deque

import pyqtgraph as pg
from PyQt6.QtCore import (
    QEasingCurve,
    QEvent,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    QUrl,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QDesktopServices,
    QLinearGradient,
    QPainter,
    QPen,
)
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QScroller,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from smart_optimizer.presentation.theme import DARK_TOKENS, LIGHT_TOKENS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_bytes(value: int | float) -> str:
    size = float(value)
    for suffix in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.1f} {suffix}"
        size /= 1024.0
    return f"{size:.1f} PB"


def _as_number(payload: dict[str, object], key: str, default: float = 0.0) -> float:
    try:
        return float(payload.get(key, default))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _format_timestamp(value: object) -> str:
    try:
        timestamp = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "Last changed: unknown"
    return "Last changed: " + datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def _shadow(widget: QWidget, blur: int = 14, y: int = 4) -> None:
    """Subtle drop-shadow — much lighter than the glassmorphism version."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    effect.setColor(QColor(0, 0, 0, 40))
    widget.setGraphicsEffect(effect)


def _enable_kinetic_scroll(scroll: QScrollArea, step: int = 20) -> None:
    """Attach QScroller kinetic physics and comfortable wheel step."""
    QScroller.grabGesture(
        scroll.viewport(),
        QScroller.ScrollerGestureType.LeftMouseButtonGesture,
    )
    scroll.verticalScrollBar().setSingleStep(step)


# ---------------------------------------------------------------------------
# EnterpriseSparkLine — tiny embedded pyqtgraph trend widget
# ---------------------------------------------------------------------------

class EnterpriseSparkLine(pg.PlotWidget):
    """A minimal single-line spark graph for embedding inside metric tiles.

    Height is fixed at 48 px; all axes, grids, and controls are hidden.
    The coloured line itself is the only visual element.
    """

    _MAX_POINTS: int = 80

    def __init__(self, color: str = "#22d3c5") -> None:
        super().__init__()
        self._color = color
        self._data: Deque[float] = deque(maxlen=self._MAX_POINTS)
        self.setMinimumHeight(80)
        self.setMinimumWidth(60)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setBackground(None)
        self.setMenuEnabled(False)
        self.setMouseEnabled(x=False, y=False)
        self.hideButtons()
        self.hideAxis("left")
        self.hideAxis("bottom")
        self.setContentsMargins(0, 0, 0, 0)
        # Build gradient fill brush.
        brush_color = QColor(color)
        brush_color.setAlpha(45)
        self._curve = self.plot(
            pen=pg.mkPen(color, width=2),
            fillLevel=0,
            brush=pg.mkBrush(brush_color),
        )

    def push(self, value: float) -> None:
        self._data.append(value)
        self._curve.setData(list(self._data))


# ---------------------------------------------------------------------------
# PremiumMessageDialog
# ---------------------------------------------------------------------------

class PremiumMessageDialog(QDialog):
    """Flat dark-themed modal confirmation / error dialog."""

    def __init__(
        self,
        title: str,
        body: str,
        metric: str | None,
        kind: str,
        parent: QWidget | None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("PremiumDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 26)
        layout.setSpacing(14)

        icon_color = {
            "success": "#22d3c5",
            "error": "#fb7185",
            "warning": "#f59e0b",
        }.get(kind, "#22d3c5")

        badge_text = {"success": "✓  SUCCESS", "error": "✕  ERROR", "warning": "⚠  WARNING"}.get(
            kind, "INFO"
        )
        icon = QLabel(badge_text)
        icon.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        icon.setStyleSheet(
            f"color: {icon_color}; font-size: 9pt; font-weight: 800; "
            f"letter-spacing: 1.2px; padding: 0px;"
        )

        title_label = QLabel(title)
        title_label.setObjectName("DialogTitle")

        body_label = QLabel(body)
        body_label.setObjectName("DialogBody")
        body_label.setWordWrap(True)

        # Horizontal rule separator.
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: #3b404c; border: 0px; max-height: 1px;")

        layout.addWidget(icon)
        layout.addWidget(sep)
        layout.addWidget(title_label)

        if metric is not None:
            metric_label = QLabel(metric)
            metric_label.setObjectName("DialogMetric")
            layout.addWidget(metric_label)

        layout.addWidget(body_label)

        button = QPushButton("Dismiss")
        button.clicked.connect(self.accept)
        layout.addWidget(button, alignment=Qt.AlignmentFlag.AlignRight)

    def exec(self) -> int:  # type: ignore[override]
        self.raise_()
        self.activateWindow()
        return super().exec()


# ---------------------------------------------------------------------------
# GlassPanel — base flat container (name kept for backwards compat)
# ---------------------------------------------------------------------------

class GlassPanel(QFrame):
    def __init__(self, title: str | None = None, subtitle: str | None = None) -> None:
        super().__init__()
        self.setObjectName("GlassPanel")
        self.layout = QVBoxLayout(self)  # type: ignore[assignment]
        self.layout.setContentsMargins(18, 14, 18, 16)
        self.layout.setSpacing(12)
        if title is not None:
            self.layout.addWidget(SectionHeader(title, subtitle))


class SectionHeader(QWidget):
    def __init__(self, title: str, subtitle: str | None = None) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(2)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        layout.addWidget(title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setObjectName("SectionSubtitle")
            sub.setWordWrap(True)
            layout.addWidget(sub)


# ---------------------------------------------------------------------------
# StatusPill
# ---------------------------------------------------------------------------

class StatusPill(QLabel):
    def __init__(self, text: str = "Idle", color: str = "#8b93a7") -> None:
        super().__init__(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumHeight(22)
        self.set_color(color)

    def set_color(self, color: str) -> None:
        self.setStyleSheet(
            f"""
            QLabel {{
                background: {color}20;
                border: 1px solid {color}55;
                color: {color};
                border-radius: 2px;
                padding: 2px 8px;
                font-size: 8pt;
                font-weight: 700;
                letter-spacing: 0.6px;
            }}
            """
        )


# ---------------------------------------------------------------------------
# MetricTile — flat enterprise style: giant centred number + uppercase label
# ---------------------------------------------------------------------------

class MetricTile(QFrame):
    """A single KPI tile: full-height big number centred, label underneath.

    Used both as a standalone tile and embedded inside dashboard layouts.
    """

    def __init__(self, title: str, caption: str, accent: str) -> None:
        super().__init__()
        self.setObjectName("MetricTile")
        self._accent = accent
        self._value_text = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._value = QLabel("—")
        self._value.setObjectName("BigNumber")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._caption = QLabel(title.upper())
        self._caption.setObjectName("TileLabel")
        self._caption.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addStretch(1)
        layout.addWidget(self._value)
        layout.addWidget(self._caption)
        layout.addStretch(1)

    def set_value(self, value: str, progress: float | None = None) -> None:
        if value != self._value_text:
            self._value_text = value
            self._value.setText(value)


# ---------------------------------------------------------------------------
# EnterpriseSummaryBar — Row 0: full-width accent strip
# ---------------------------------------------------------------------------

class EnterpriseSummaryBar(QFrame):
    """Full-width summary strip with left-accent border.

    Shows several key/value pairs in a horizontal row.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("EnterpriseBar")
        self.setFixedHeight(68)
        row = QHBoxLayout(self)
        row.setContentsMargins(22, 0, 22, 0)
        row.setSpacing(0)

        self._cells: dict[str, tuple[QLabel, QLabel]] = {}
        specs = [
            ("files_checked",       "FILES CHECKED",      "#22d3c5"),
            ("files_discovered",    "FILES FOUND",        "#e8eaf0"),
            ("storage_reclaimable", "JUNK SPACE",         "#3ee0a1"),
            ("duplicate_groups",    "DUPLICATE GROUPS",   "#f59e0b"),
        ]
        for i, (key, label, color) in enumerate(specs):
            if i > 0:
                div = QFrame()
                div.setFrameShape(QFrame.Shape.VLine)
                div.setStyleSheet(f"background: #3b404c; max-width: 1px;")
                row.addWidget(div)
            cell = self._make_cell(label, color)
            row.addWidget(cell, 1)
            # Store label refs for later update.
            self._cells[key] = (
                cell.findChild(QLabel, "SummaryValue"),   # type: ignore[assignment]
                cell.findChild(QLabel, "SummaryKey"),     # type: ignore[assignment]
            )

    @staticmethod
    def _make_cell(label: str, color: str) -> QWidget:
        cell = QWidget()
        v = QVBoxLayout(cell)
        v.setContentsMargins(24, 10, 24, 10)
        v.setSpacing(1)
        val = QLabel("—")
        val.setObjectName("SummaryValue")
        val.setStyleSheet(f"color: {color}; font-size: 14pt; font-weight: 700;")
        key = QLabel(label)
        key.setObjectName("SummaryKey")
        v.addWidget(val)
        v.addWidget(key)
        return cell

    def update_metrics(self, payload: dict[str, object]) -> None:
        fps = int(_as_number(payload, "files_processed"))
        found = int(_as_number(payload, "files_discovered"))
        junk = _as_number(payload, "storage_reclaimable_bytes")
        groups = int(_as_number(payload, "duplicate_groups", 0))

        # We store references directly in _cells as (value_label, key_label).
        # findChild is done once in __init__; we iterate by key here.
        values = {
            "files_checked": str(fps),
            "files_discovered": f"{found:,}",
            "storage_reclaimable": format_bytes(junk),
            "duplicate_groups": str(groups),
        }
        for key, (val_lbl, _) in self._cells.items():
            if val_lbl is not None:
                val_lbl.setText(values.get(key, "—"))

    def _set_cell_value(self, key: str, text: str) -> None:
        pair = self._cells.get(key)
        if pair and pair[0] is not None:
            pair[0].setText(text)


# ---------------------------------------------------------------------------
# EnterpriseTile — Row 1: big number + optional spark graph
# ---------------------------------------------------------------------------

class EnterpriseTile(QFrame):
    """One of four tiles in Row 1 of the Rapid7-style grid.

    Shows a very large centred number, an ALL-CAPS label below it,
    and an optional embedded EnterpriseSparkLine at the bottom.
    """

    def __init__(self, title: str, accent: str, spark: bool = False) -> None:
        super().__init__()
        self.setObjectName("EnterpriseTile")
        self.setMinimumHeight(140)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 14)
        layout.setSpacing(4)

        # Top-left header label (small, muted).
        header = QLabel(title.upper())
        header.setObjectName("TileLabel")
        header.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        # Centre — the very large number.
        self._value = QLabel("—")
        self._value.setObjectName("BigNumber")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value.setStyleSheet(f"color: {accent};")

        layout.addWidget(header)
        layout.addWidget(self._value, 1)

        # Optional spark line at the bottom.
        self._spark: EnterpriseSparkLine | None = None
        if spark:
            self._spark = EnterpriseSparkLine(accent)
            layout.addWidget(self._spark)

    def set_value(self, value: str) -> None:
        self._value.setText(value)

    def push_spark(self, value: float) -> None:
        if self._spark is not None:
            self._spark.push(value)


# ---------------------------------------------------------------------------
# EnterpriseStatBar — Row 2: label + flat bar + value
# ---------------------------------------------------------------------------

class EnterpriseStatBar(QFrame):
    """A wide horizontal stat row: metric name on the left, flat progress bar
    in the middle, numeric value on the right.
    """

    def __init__(self, title: str, accent: str, unit: str = "") -> None:
        super().__init__()
        self.setObjectName("EnterpriseStatBar")
        self.setFixedHeight(62)
        self._unit = unit

        row = QHBoxLayout(self)
        row.setContentsMargins(20, 12, 20, 12)
        row.setSpacing(16)

        self._label = QLabel(title.upper())
        self._label.setObjectName("TileLabel")
        self._label.setFixedWidth(160)

        self._bar = QProgressBar()
        self._bar.setRange(0, 1000)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(8)
        self._bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: #2d3039;
                border: 0px;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {accent};
                border-radius: 2px;
            }}
            """
        )

        self._value_label = QLabel("—")
        self._value_label.setObjectName("SummaryValue")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._value_label.setFixedWidth(110)
        self._value_label.setStyleSheet(f"color: {accent}; font-size: 11pt; font-weight: 700;")

        row.addWidget(self._label)
        row.addWidget(self._bar, 1)
        row.addWidget(self._value_label)

    def set_value(self, display: str, fraction: float) -> None:
        """*fraction* is 0.0–1.0."""
        self._value_label.setText(display)
        self._bar.setValue(int(max(0.0, min(1.0, fraction)) * 1000))


# ---------------------------------------------------------------------------
# MetricsDashboard — 3-row Rapid7 grid
# ---------------------------------------------------------------------------

class MetricsDashboard(GlassPanel):
    """
    Layout:
        Row 0  EnterpriseSummaryBar          (full width, accent strip)
        Row 1  4 × EnterpriseTile            (big number ± spark)
        Row 2  2 × EnterpriseStatBar         (label + flat bar + value)
    """

    def __init__(self) -> None:
        super().__init__(None)  # No GlassPanel header — we provide our own.
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(1)           # 1 px gap between rows (border lines)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(1)

        # ---- Row 0: summary bar ----
        self._summary = EnterpriseSummaryBar()
        grid.addWidget(self._summary, 0, 0, 1, 4)

        # ---- Row 1: four tiles ----
        self._t_days    = EnterpriseTile("Days Since Last Scan", "#e8eaf0", spark=False)
        self._t_robots  = EnterpriseTile("Robots Busy",          "#f59e0b", spark=False)
        self._t_waiting = EnterpriseTile("Files Waiting",        "#22d3c5", spark=True)
        self._t_failed  = EnterpriseTile("Failed Reads",         "#fb7185", spark=True)

        grid.addWidget(self._t_days, 1, 0)
        grid.addWidget(self._t_robots, 1, 1)
        grid.addWidget(self._t_waiting, 1, 2)
        grid.addWidget(self._t_failed, 1, 3)

        # ---- Row 2: stat bars ----
        self._bar_junk  = EnterpriseStatBar("Junk Space to Free Up", "#3ee0a1")
        self._bar_speed = EnterpriseStatBar("Scanning Speed",        "#22d3c5", unit="f/s")
        self._bar_mem   = EnterpriseStatBar("App Memory",            "#60a5fa", unit="MB")

        grid.addWidget(self._bar_junk, 2, 0, 1, 4)
        grid.addWidget(self._bar_speed, 3, 0, 1, 4)
        grid.addWidget(self._bar_mem, 4, 0, 1, 4)

        # Enforce enterprise grid scaling
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)
        grid.setRowStretch(0, 0)
        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 0)
        grid.setRowStretch(3, 0)
        grid.setRowStretch(4, 0)

        self.layout.addLayout(grid)

        # Internal state for "days since last scan" (not in live payload).
        self._last_scan_day: str = "—"

    def update_metrics(self, payload: dict[str, object]) -> None:
        fps        = _as_number(payload, "files_per_second")
        utilization = _as_number(payload, "thread_utilization") * 100.0
        queue_depth = int(_as_number(payload, "queue_depth"))
        failed     = int(_as_number(payload, "failed"))
        memory     = _as_number(payload, "memory_usage_mb")
        reclaimable = _as_number(payload, "storage_reclaimable_bytes")
        processed  = int(_as_number(payload, "files_processed"))
        discovered = int(_as_number(payload, "files_discovered"))

        # ---- Summary bar ----
        self._summary.update_metrics(payload)

        # ---- Row 1 tiles ----
        self._t_days.set_value(self._last_scan_day)
        self._t_robots.set_value(f"{utilization:.0f}%")
        self._t_waiting.set_value(f"{queue_depth:,}")
        self._t_waiting.push_spark(float(queue_depth))
        self._t_failed.set_value(f"{failed:,}")
        self._t_failed.push_spark(float(failed))

        # ---- Row 2 stat bars ----
        self._bar_junk.set_value(
            format_bytes(reclaimable),
            min(1.0, reclaimable / 5_000_000_000),
        )
        self._bar_speed.set_value(
            f"{fps:.0f} f/s",
            min(1.0, fps / 500),
        )
        self._bar_mem.set_value(
            f"{memory:.0f} MB",
            min(1.0, memory / 800),
        )


# ---------------------------------------------------------------------------
# WorkerCard
# ---------------------------------------------------------------------------

class WorkerCard(QFrame):
    def __init__(self, worker_id: int) -> None:
        super().__init__()
        self.setObjectName("WorkerCard")
        self.setMinimumWidth(200)
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        self._title = QLabel(f"Robot {worker_id + 1:02d}")
        self._title.setObjectName("SectionTitle")
        self._pill = StatusPill("Waiting", "#8b93a7")
        header.addWidget(self._title)
        header.addStretch(1)
        header.addWidget(self._pill)

        self._file = QLabel("Ready to check files")
        self._file.setObjectName("SmallLabel")
        self._file.setWordWrap(True)

        self._counts = QLabel("0 checked / 0 need attention")
        self._counts.setObjectName("MetricCaption")

        # Flat progress bar instead of doughnut.
        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(4)

        layout.addLayout(header)
        layout.addWidget(self._file)
        layout.addWidget(self._counts)
        layout.addWidget(self._bar)

    def update_snapshot(self, snapshot: dict[str, object]) -> None:
        state = str(snapshot.get("state", "Waiting"))
        current_file = str(snapshot.get("current_file") or "")
        processed = int(_as_number(snapshot, "processed_count"))
        failed = int(_as_number(snapshot, "failed_count"))

        color = {
            "Running": "#3ee0a1",
            "Waiting": "#8b93a7",
            "Blocked": "#f59e0b",
            "Stopped": "#555d6e",
        }.get(state, "#8b93a7")

        friendly_state = {
            "Running": "RUNNING",
            "Waiting": "IDLE",
            "Blocked": "PAUSED",
            "Stopped": "STOPPED",
        }.get(state, state.upper())

        self._pill.setText(friendly_state)
        self._pill.set_color(color)
        self._file.setText(current_file if current_file else "Idle — waiting for files")
        self._counts.setText(f"{processed:,} checked  /  {failed:,} failed")
        self._bar.setValue(100 if state == "Running" else 20 if state == "Waiting" else 0)
        self._bar.setStyleSheet(
            f"""
            QProgressBar {{
                background: #2d3039; border: 0px; border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background: {color}; border-radius: 2px;
            }}
            """
        )


class WorkerPanel(GlassPanel):
    def __init__(self) -> None:
        super().__init__(
            "Scanning Robots",
            "Each robot checks files in the background while the app stays responsive.",
        )
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(1)
        self._grid.setVerticalSpacing(1)
        self._cards: dict[int, WorkerCard] = {}
        self.layout.addLayout(self._grid)

    def update_workers(self, payload: dict[str, object]) -> None:
        workers = payload.get("workers", [])
        if not isinstance(workers, list):
            return
        for index, item in enumerate(workers):
            if not isinstance(item, dict):
                continue
            worker_id = int(item.get("worker_id", index))
            card = self._cards.get(worker_id)
            if card is None:
                card = WorkerCard(worker_id)
                self._cards[worker_id] = card
                self._grid.addWidget(card, worker_id // 3, worker_id % 3)
            card.update_snapshot(item)


# ---------------------------------------------------------------------------
# LiveGraphs
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class SeriesPoint:
    tick: int
    value: float


class LiveGraphs(GlassPanel):
    def __init__(self) -> None:
        super().__init__("Live Scan Activity", "Trend graphs for scan speed and queue depth.")
        pg.setConfigOptions(antialias=True, foreground="#555d6e")

        row = QHBoxLayout()
        row.setSpacing(1)

        self._throughput_plot = self._plot("SCANNING SPEED")
        self._queue_plot = self._plot("FILES WAITING")

        self._throughput_curve = self._throughput_plot.plot(
            pen=pg.mkPen("#22d3c5", width=2),
            fillLevel=0,
            brush=self._area_brush("#22d3c5"),
        )
        self._queue_curve = self._queue_plot.plot(
            pen=pg.mkPen("#f59e0b", width=2),
            fillLevel=0,
            brush=self._area_brush("#f59e0b"),
        )

        row.addWidget(self._throughput_plot, stretch=1)
        row.addWidget(self._queue_plot, stretch=1)
        self.layout.addLayout(row)

        self._tick = 0
        self._throughput: Deque[SeriesPoint] = deque(maxlen=160)
        self._queue_series: Deque[SeriesPoint] = deque(maxlen=160)

    def apply_theme(self, dark: bool) -> None:
        tokens = DARK_TOKENS if dark else LIGHT_TOKENS
        for plot in (self._throughput_plot, self._queue_plot):
            plot.setBackground(None)
            plot.showGrid(x=False, y=False)
            plot.getAxis("left").setPen(pg.mkPen(tokens.graph_axis))
            plot.getAxis("bottom").setPen(pg.mkPen(tokens.graph_axis))
            plot.hideAxis("left")
            plot.hideAxis("bottom")

    def update_metrics(self, payload: dict[str, object]) -> None:
        self._tick += 1
        self._throughput.append(SeriesPoint(self._tick, _as_number(payload, "files_per_second")))
        self._queue_series.append(SeriesPoint(self._tick, _as_number(payload, "queue_depth")))
        self._throughput_curve.setData(
            [p.tick for p in self._throughput],
            [p.value for p in self._throughput],
        )
        self._queue_curve.setData(
            [p.tick for p in self._queue_series],
            [p.value for p in self._queue_series],
        )

    @staticmethod
    def _plot(title: str) -> pg.PlotWidget:
        plot = pg.PlotWidget()
        plot.setMinimumHeight(120)
        plot.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        plot.setTitle(title, color="#555d6e", size="9pt")
        plot.setMenuEnabled(False)
        plot.setMouseEnabled(x=False, y=False)
        plot.hideButtons()
        plot.setBackground(None)
        plot.hideAxis("left")
        plot.hideAxis("bottom")
        plot.setContentsMargins(0, 0, 0, 0)
        return plot

    @staticmethod
    def _area_brush(color: str) -> QBrush:
        gradient = QLinearGradient(0, 0, 0, 240)
        top = QColor(color)
        top.setAlpha(60)
        transparent = QColor(color)
        transparent.setAlpha(8)
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(1.0, transparent)
        return QBrush(gradient)


# ---------------------------------------------------------------------------
# ExecutionTimeline
# ---------------------------------------------------------------------------

class ExecutionTimeline(GlassPanel):
    def __init__(self) -> None:
        super().__init__(
            "Robot Work Timeline",
            "Chronological log of files checked — newest jobs auto-scroll to the right.",
        )
        self._job_counter = 0
        self._lanes: dict[int, QHBoxLayout] = {}
        self._lane_widgets: dict[int, QFrame] = {}

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        _enable_kinetic_scroll(self._scroll, step=20)

        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(1)
        self._container_layout.addStretch(1)
        self._scroll.setWidget(self._container)

        self._empty = QLabel("Timeline will populate when files are processed.")
        self._empty.setObjectName("MutedText")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setMinimumHeight(64)

        self.layout.addWidget(self._empty)
        self.layout.addWidget(self._scroll)
        self._scroll.setVisible(False)

    def reset(self) -> None:
        self._job_counter = 0
        self._lanes.clear()
        self._lane_widgets.clear()
        while self._container_layout.count() > 1:
            item = self._container_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._empty.setVisible(True)
        self._scroll.setVisible(False)

    def add_job(self, payload: dict[str, object]) -> None:
        worker_id = int(_as_number(payload, "worker_id", 0))
        path = str(payload.get("path", ""))
        error = payload.get("error")
        job_id = str(payload.get("job_id", ""))[:8]
        self._job_counter += 1

        lane = self._lane_for(worker_id)
        block = QFrame()
        block.setObjectName("TimelineBlock")
        block.setProperty("failed", "true" if error else "false")
        block.setMinimumWidth(140)
        block.setMaximumWidth(210)
        block.setMinimumHeight(52)

        blayout = QVBoxLayout(block)
        blayout.setContentsMargins(8, 6, 8, 6)
        blayout.setSpacing(2)

        title = QLabel(f"#{self._job_counter}  {job_id}")
        title.setObjectName("SectionTitle")
        file_name = path.rsplit("\\", 1)[-1] if "\\" in path else path.rsplit("/", 1)[-1]
        detail = QLabel(file_name if file_name else "file")
        detail.setObjectName("SmallLabel")
        detail.setToolTip(path)
        blayout.addWidget(title)
        blayout.addWidget(detail)

        lane.addWidget(block)
        self._empty.setVisible(False)
        self._scroll.setVisible(True)
        self._scroll.horizontalScrollBar().setValue(
            self._scroll.horizontalScrollBar().maximum()
        )

    def _lane_for(self, worker_id: int) -> QHBoxLayout:
        if worker_id in self._lanes:
            return self._lanes[worker_id]
        row = QFrame()
        row.setObjectName("TimelineLane")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(10, 8, 10, 8)
        row_layout.setSpacing(6)
        label = QLabel(f"R{worker_id + 1:02d}")
        label.setObjectName("SectionTitle")
        label.setFixedWidth(42)
        row_layout.addWidget(label)
        lane_layout = QHBoxLayout()
        lane_layout.setSpacing(6)
        row_layout.addLayout(lane_layout)
        row_layout.addStretch(1)
        self._container_layout.insertWidget(self._container_layout.count() - 1, row)
        self._lanes[worker_id] = lane_layout
        self._lane_widgets[worker_id] = row
        return lane_layout


# ---------------------------------------------------------------------------
# SchedulerPanel
# ---------------------------------------------------------------------------

class SchedulerPanel(GlassPanel):
    def __init__(self) -> None:
        super().__init__("Work Planner", "Files waiting, active, completed, and failed.")
        self._grid = QGridLayout()
        self._grid.setHorizontalSpacing(1)
        self._grid.setVerticalSpacing(1)
        self._labels: dict[str, MetricTile] = {
            "queued":       MetricTile("Files Waiting",   "not checked yet",           "#f59e0b"),
            "running":      MetricTile("Being Checked",   "robots working now",         "#22d3c5"),
            "completed":    MetricTile("Done",             "files already checked",     "#3ee0a1"),
            "failed":       MetricTile("Need Attention",   "files the app could not read","#fb7185"),
            "boosted_jobs": MetricTile("Fair Turns",       "older files moved forward", "#f59e0b"),
            "oldest_wait_ms": MetricTile("Longest Wait",  "oldest file still waiting", "#8b93a7"),
        }
        for index, tile in enumerate(self._labels.values()):
            self._grid.addWidget(tile, index // 3, index % 3)
        self.layout.addLayout(self._grid)

    def update_scheduler(self, payload: dict[str, object]) -> None:
        queued    = int(_as_number(payload, "queued"))
        running   = int(_as_number(payload, "running"))
        completed = int(_as_number(payload, "completed"))
        failed    = int(_as_number(payload, "failed"))
        boosted   = int(_as_number(payload, "boosted_jobs"))
        oldest    = _as_number(payload, "oldest_wait_ms")
        self._labels["queued"].set_value(f"{queued:,}")
        self._labels["running"].set_value(f"{running:,}")
        self._labels["completed"].set_value(f"{completed:,}")
        self._labels["failed"].set_value(f"{failed:,}")
        self._labels["boosted_jobs"].set_value(f"{boosted:,}")
        self._labels["oldest_wait_ms"].set_value(f"{oldest:.0f} ms")


# ---------------------------------------------------------------------------
# DuplicateTable
# ---------------------------------------------------------------------------

class DuplicateTable(GlassPanel):
    def __init__(self) -> None:
        super().__init__(
            "Duplicate Finder",
            "Files with identical content. Review before removing.",
        )
        self._delete_handler: Callable | None = None
        self._empty = QLabel("No exact duplicates yet. Start a scan to find repeated files.")
        self._empty.setObjectName("MutedText")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setMinimumHeight(120)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.viewport().setAttribute(Qt.WidgetAttribute.WA_StaticContents, True)
        _enable_kinetic_scroll(self._scroll, step=20)

        self._container = QWidget()
        self._container.setAttribute(Qt.WidgetAttribute.WA_StaticContents, True)
        self._cards = QVBoxLayout(self._container)
        self._cards.setContentsMargins(0, 0, 0, 0)
        self._cards.setSpacing(1)
        self._cards.addStretch(1)
        self._scroll.setWidget(self._container)
        self._scroll.setVisible(False)
        self._rendered_signature = ""

        self.layout.addWidget(self._empty)
        self.layout.addWidget(self._scroll, 1)

    def set_delete_handler(self, handler: Callable) -> None:
        self._delete_handler = handler

    def update_groups(self, payload: dict[str, object]) -> None:
        groups = payload.get("groups", [])
        if not isinstance(groups, list):
            return
        signature = "|".join(
            str(g.get("group_id", "")) + ":" + str(len(g.get("files", [])))
            for g in groups
            if isinstance(g, dict)
        )
        if signature == self._rendered_signature:
            return
        self._rendered_signature = signature
        self._empty.setVisible(len(groups) == 0)
        self._scroll.setVisible(len(groups) > 0)
        self._clear_cards()
        valid = [g for g in groups if isinstance(g, dict)]
        for index, group in enumerate(valid[:120]):
            card = DuplicateGroupCard(
                group,
                expanded=index == 0,
                delete_handler=self._delete_handler,
            )
            self._cards.insertWidget(self._cards.count() - 1, card)
        if len(valid) > 120:
            more = QLabel(
                f"Showing first 120 of {len(valid):,} groups — most critical first."
            )
            more.setObjectName("MutedText")
            more.setAlignment(Qt.AlignmentFlag.AlignCenter)
            more.setMinimumHeight(48)
            self._cards.insertWidget(self._cards.count() - 1, more)

    def _clear_cards(self) -> None:
        while self._cards.count() > 1:
            item = self._cards.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()


# ---------------------------------------------------------------------------
# DuplicateGroupCard
# ---------------------------------------------------------------------------

class DuplicateGroupCard(QFrame):
    def __init__(
        self,
        group: dict[str, object],
        expanded: bool,
        delete_handler: Callable | None,
    ) -> None:
        super().__init__()
        self.setObjectName("DuplicateGroupCard")
        self._group = group
        self._delete_handler = delete_handler
        self._expanded = expanded
        self._rows_built = False
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        header = QHBoxLayout()
        risk_score = int(_as_number(group, "risk_score"))
        risk_level = str(group.get("risk_level", "Low"))
        files = group.get("files", [])
        file_count = len(files) if isinstance(files, list) else 0

        self._toggle = QToolButton()
        self._toggle.setObjectName("CollapseButton")
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self._toggle.setText(f"Exact Match — {file_count} files")
        self._toggle.clicked.connect(self._toggle_rows)

        header.addWidget(self._toggle, 1)
        header.addWidget(StatusPill(f"Risk {risk_score}", self._risk_color(risk_score)))
        header.addWidget(StatusPill(risk_level, self._risk_color(risk_score)))
        header.addWidget(QLabel(format_bytes(_as_number(group, "size_bytes"))))
        header.addWidget(QLabel(f"{format_bytes(_as_number(group, 'reclaimable_bytes'))} recoverable"))
        layout.addLayout(header)

        full_hash = str(group.get("full_hash", ""))
        self._details = QLabel(f"Hash: {full_hash}")
        self._details.setObjectName("HashLabel")
        self._details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._details)

        self._rows = QWidget()
        self._rows_layout = QVBoxLayout(self._rows)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(1)
        layout.addWidget(self._rows)
        self._rows.setVisible(expanded)
        if expanded:
            self._build_rows()

    def _toggle_rows(self) -> None:
        self._expanded = not self._expanded
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if self._expanded else Qt.ArrowType.RightArrow
        )
        if self._expanded and not self._rows_built:
            self._build_rows()
        self._rows.setVisible(self._expanded)

    def _build_rows(self) -> None:
        files = self._group.get("files", [])
        if not isinstance(files, list):
            return
        for file_data in files[:40]:
            if isinstance(file_data, dict):
                self._rows_layout.addWidget(
                    DuplicateFileRow(
                        file_data,
                        int(_as_number(self._group, "risk_score")),
                        self._delete_handler,
                    )
                )
        if len(files) > 40:
            label = QLabel(f"{len(files) - 40:,} more files not shown.")
            label.setObjectName("MutedText")
            self._rows_layout.addWidget(label)
        self._rows_built = True

    @staticmethod
    def _risk_color(score: int) -> str:
        if score >= 80:
            return "#fb7185"
        if score >= 55:
            return "#f59e0b"
        if score >= 25:
            return "#60a5fa"
        return "#3ee0a1"


# ---------------------------------------------------------------------------
# DuplicateFileRow
# ---------------------------------------------------------------------------

class DuplicateFileRow(QFrame):
    def __init__(
        self,
        file_data: dict[str, object],
        risk_score: int,
        delete_handler: Callable | None,
    ) -> None:
        super().__init__()
        self.setObjectName("DuplicateFileRow")
        self._file_data = file_data
        self._risk_score = risk_score
        self._delete_handler = delete_handler
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        path = str(file_data.get("path", ""))
        extension = str(file_data.get("extension", "") or "file")
        size = int(_as_number(file_data, "size_bytes"))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 7, 10, 7)
        layout.setSpacing(10)

        icon = QLabel(self._icon_text(extension))
        icon.setFixedWidth(32)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setObjectName("SectionTitle")

        text = QVBoxLayout()
        name = QLabel(path.rsplit("\\", 1)[-1] if "\\" in path else path.rsplit("/", 1)[-1])
        name.setObjectName("SectionTitle")
        modified = _format_timestamp(file_data.get("modified_at"))
        meta = QLabel(f"{format_bytes(size)}  —  {modified}  —  {path}")
        meta.setObjectName("SmallLabel")
        meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.addWidget(name)
        text.addWidget(meta)

        actions = QHBoxLayout()
        actions.setSpacing(4)
        open_file   = self._action_button("Open",   QStyle.StandardPixmap.SP_FileIcon)
        open_folder = self._action_button("Folder", QStyle.StandardPixmap.SP_DirIcon)
        delete      = self._action_button("Remove", QStyle.StandardPixmap.SP_TrashIcon, danger=True)
        open_file.clicked.connect(self._open_file)
        open_folder.clicked.connect(self._open_folder)
        delete.clicked.connect(self._confirm_delete)
        actions.addWidget(open_file)
        actions.addWidget(open_folder)
        actions.addWidget(delete)

        layout.addWidget(icon)
        layout.addLayout(text, 1)
        layout.addLayout(actions)

    def _action_button(
        self,
        text: str,
        icon: QStyle.StandardPixmap,
        danger: bool = False,
    ) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("DangerButton" if danger else "SecondaryButton")
        button.setIcon(QApplication.style().standardIcon(icon))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip(text)
        return button

    def _open_file(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._file_data.get("path", ""))))

    def _open_folder(self) -> None:
        path = str(self._file_data.get("path", ""))
        folder = path.rsplit("\\", 1)[0] if "\\" in path else path.rsplit("/", 1)[0]
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _confirm_delete(self) -> None:
        path = str(self._file_data.get("path", ""))
        size = int(_as_number(self._file_data, "size_bytes"))
        response = QMessageBox.question(
            self,
            "Remove duplicate file",
            "This will move the selected file to the Recycle Bin.\n\n"
            f"Risk score: {self._risk_score}\n"
            f"File: {path}\n\n"
            "Continue?",
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.Cancel,
        )
        if response != QMessageBox.StandardButton.Yes or self._delete_handler is None:
            return
        success, _message = self._delete_handler(path, size, self._risk_score)
        if success:
            self.deleteLater()

    @staticmethod
    def _icon_text(extension: str) -> str:
        clean = extension.replace(".", "").upper()
        return clean[:4] if clean else "FILE"


# ---------------------------------------------------------------------------
# SummaryStatCard / AnalyticsPanel
# ---------------------------------------------------------------------------

class SummaryStatCard(QFrame):
    def __init__(self, title: str, helper: str, accent: str) -> None:
        super().__init__()
        self.setObjectName("MetricTile")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(6)

        label = QLabel(title.upper())
        label.setObjectName("TileLabel")
        self._value = QLabel("—")
        self._value.setObjectName("BigNumber")
        self._value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._value.setStyleSheet(f"color: {accent};")
        note = QLabel(helper)
        note.setObjectName("SmallLabel")
        note.setWordWrap(True)

        layout.addWidget(label)
        layout.addWidget(self._value)
        layout.addWidget(note)

    def set_value(self, value: str) -> None:
        self._value.setText(value)


class AnalyticsPanel(GlassPanel):
    def __init__(self) -> None:
        super().__init__("Insights", "Plain-language summary of what the scan found.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(1)
        grid.setVerticalSpacing(1)
        self._cards = {
            "wasted_space": SummaryStatCard("Wasted Space",  "Duplicate junk you can free up.", "#3ee0a1"),
            "files_found":  SummaryStatCard("Files Found",   "Total files in the selected folder.", "#22d3c5"),
            "files_checked":SummaryStatCard("Files Checked", "Already reviewed by scanning robots.", "#60a5fa"),
            "files_waiting":SummaryStatCard("Files Waiting", "Still queued for review.", "#f59e0b"),
        }
        for index, card in enumerate(self._cards.values()):
            grid.addWidget(card, index // 2, index % 2)
        self.layout.addLayout(grid)

    def update_metrics(self, payload: dict[str, object]) -> None:
        self._cards["wasted_space"].set_value(
            format_bytes(_as_number(payload, "storage_reclaimable_bytes"))
        )
        self._cards["files_found"].set_value(
            f"{int(_as_number(payload, 'files_discovered')):,}"
        )
        self._cards["files_checked"].set_value(
            f"{int(_as_number(payload, 'files_processed')):,}"
        )
        self._cards["files_waiting"].set_value(
            f"{int(_as_number(payload, 'queue_depth')):,}"
        )


# ---------------------------------------------------------------------------
# ToggleSwitch / SettingsRow / SettingsPanel
# ---------------------------------------------------------------------------

class ToggleSwitch(QToolButton):
    toggled_value = pyqtSignal(bool)

    def __init__(self, checked: bool = False) -> None:
        super().__init__()
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._emit_value)
        self._sync_text()

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        super().setChecked(checked)
        self._sync_text()

    def _emit_value(self) -> None:
        self._sync_text()
        self.toggled_value.emit(self.isChecked())

    def _sync_text(self) -> None:
        self.setText("ON" if self.isChecked() else "OFF")
        self.setObjectName("SecondaryButton")


class SettingsRow(QFrame):
    def __init__(self, title: str, helper: str, checked: bool) -> None:
        super().__init__()
        self.setObjectName("MetricTile")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)
        text = QVBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        helper_label = QLabel(helper)
        helper_label.setObjectName("SmallLabel")
        helper_label.setWordWrap(True)
        text.addWidget(title_label)
        text.addWidget(helper_label)
        self.toggle = ToggleSwitch(checked)
        layout.addLayout(text, 1)
        layout.addWidget(self.toggle)


class SettingsPanel(GlassPanel):
    theme_changed = pyqtSignal(bool)
    include_hidden_changed = pyqtSignal(bool)

    def __init__(self, dark_mode: bool = True, include_hidden: bool = False) -> None:
        super().__init__("Settings", "Scan options and appearance.")
        self._dark_row = SettingsRow(
            "Dark Mode",
            "Use the dark enterprise-dashboard appearance.",
            dark_mode,
        )
        self._hidden_row = SettingsRow(
            "Show Hidden Files",
            "Include system and hidden files in the next scan.",
            include_hidden,
        )
        self._system_note = QLabel(
            "Protected system folders are always excluded to keep your computer safe."
        )
        self._system_note.setObjectName("MutedText")
        self._system_note.setWordWrap(True)
        self.layout.addWidget(self._dark_row)
        self.layout.addWidget(self._hidden_row)
        self.layout.addWidget(self._system_note)
        self._dark_row.toggle.toggled_value.connect(self.theme_changed.emit)
        self._hidden_row.toggle.toggled_value.connect(self.include_hidden_changed.emit)

    def set_dark_mode(self, enabled: bool) -> None:
        self._dark_row.toggle.setChecked(enabled)

    def set_include_hidden(self, enabled: bool) -> None:
        self._hidden_row.toggle.setChecked(enabled)


# ---------------------------------------------------------------------------
# Toast / ToastManager — signal-driven lifecycle, no C++ race conditions
# ---------------------------------------------------------------------------

class Toast(QFrame):
    """Flat notification banner with signal-driven cleanup."""

    toast_closed = pyqtSignal(object)

    def __init__(self, message: str, kind: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        colors = {
            "success": "#3ee0a1",
            "error": "#fb7185",
            "warning": "#f59e0b",
            "info": "#60a5fa",
        }
        color = colors.get(kind, colors["info"])
        icons = {"success": "✓", "error": "✕", "warning": "⚠", "info": "ℹ"}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(10)

        # Left accent bar.
        accent_bar = QFrame()
        accent_bar.setFixedWidth(3)
        accent_bar.setStyleSheet(f"background: {color}; border: 0px;")

        dot = QLabel(icons.get(kind, "ℹ"))
        dot.setStyleSheet(f"color: {color}; font-size: 11pt; font-weight: 800;")
        label = QLabel(message)
        label.setWordWrap(True)

        layout.addWidget(accent_bar)
        layout.addWidget(dot)
        layout.addWidget(label, 1)
        self.setFixedWidth(360)

        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)
        self._animation = QPropertyAnimation(self._opacity, b"opacity", self)
        self._animation.setDuration(220)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._hide_connected = False

    def show_animated(self) -> None:
        self.show()
        self._animation.stop()
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.start()
        QTimer.singleShot(4000, self._safe_hide)

    def _safe_hide(self) -> None:
        try:
            if not self.isVisible():
                return
        except RuntimeError:
            return
        self.hide_animated()

    def hide_animated(self) -> None:
        if self._hide_connected:
            return
        self._hide_connected = True
        self._animation.stop()
        self._animation.setStartValue(self._opacity.opacity())
        self._animation.setEndValue(0.0)
        self._animation.finished.connect(self._on_hide_finished)
        self._animation.start()

    def _on_hide_finished(self) -> None:
        self.toast_closed.emit(self)
        self.deleteLater()


class ToastManager:
    def __init__(self, parent: QWidget) -> None:
        self._parent = parent
        self._toasts: list[Toast] = []

    def _on_toast_closed(self, toast: Toast) -> None:
        try:
            self._toasts.remove(toast)
        except ValueError:
            pass
        self._layout_toasts()

    def show(self, message: str, kind: str = "info") -> None:
        toast = Toast(message, kind, self._parent)
        toast.toast_closed.connect(self._on_toast_closed)
        self._toasts.append(toast)
        toast.show_animated()
        self._layout_toasts()

    def _layout_toasts(self) -> None:
        margin = 20
        for index, toast in enumerate(reversed(self._toasts)):
            try:
                toast.adjustSize()
                x = self._parent.width() - toast.width() - margin
                y = (
                    self._parent.height()
                    - toast.height()
                    - margin
                    - index * (toast.height() + 8)
                )
                toast.move(max(margin, x), y)
            except RuntimeError:
                pass
