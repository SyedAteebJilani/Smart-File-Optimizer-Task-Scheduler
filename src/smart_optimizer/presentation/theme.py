"""
presentation/theme.py
=====================
Design tokens and Qt stylesheets for the Smart File Cleaner dashboard.

Revision (2026-06-03): Overhauled to match a flat Rapid7-style enterprise
dark-mode UI. Glassmorphism and rounded corners are removed. All panels use
sharp 0 px radius; only interactive controls (buttons, inputs) use 4 px for
a slight refinement without appearing "bubbly". Colour tokens updated to
Rapid7-reference values.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ThemeTokens:
    name: str
    app_bg: str
    sidebar_bg: str
    panel_bg: str
    panel_alt: str
    card_bg: str
    card_hover: str
    border: str
    text: str
    muted: str
    faint: str
    primary: str
    primary_hover: str
    success: str
    warning: str
    danger: str
    graph_grid: str
    graph_axis: str


# ---------------------------------------------------------------------------
# Rapid7-reference dark tokens
# ---------------------------------------------------------------------------
DARK_TOKENS = ThemeTokens(
    name="dark",
    app_bg="#1b1d22",
    sidebar_bg="#1e2027",
    panel_bg="#252830",
    panel_alt="#2d3039",
    card_bg="#252830",
    card_hover="#2d3039",
    border="#3b404c",
    text="#e8eaf0",
    muted="#8b93a7",
    faint="#555d6e",
    primary="#22d3c5",
    primary_hover="#1bb8ab",
    success="#3ee0a1",
    warning="#f59e0b",
    danger="#fb7185",
    graph_grid="#2d3039",
    graph_axis="#555d6e",
)

# ---------------------------------------------------------------------------
# Light fallback tokens (kept minimal — dark is the primary experience)
# ---------------------------------------------------------------------------
LIGHT_TOKENS = ThemeTokens(
    name="light",
    app_bg="#f0f2f5",
    sidebar_bg="#ffffff",
    panel_bg="#ffffff",
    panel_alt="#f5f7fa",
    card_bg="#ffffff",
    card_hover="#edf0f5",
    border="#d0d5df",
    text="#1a1d24",
    muted="#5f6b7c",
    faint="#9aa3b0",
    primary="#0d9f96",
    primary_hover="#0b8880",
    success="#168f61",
    warning="#b66b00",
    danger="#c3445a",
    graph_grid="#e5e8ef",
    graph_axis="#9aa3b0",
)


def build_style(tokens: ThemeTokens) -> str:
    return f"""
    * {{
        font-family: "Segoe UI", "Inter", Arial, sans-serif;
        font-size: 10pt;
        letter-spacing: 0px;
    }}

    /* ---------------------------------------------------------------
       Root / app chrome
    --------------------------------------------------------------- */
    QMainWindow, QWidget#AppRoot {{
        background: {tokens.app_bg};
        color: {tokens.text};
    }}

    QWidget#Sidebar {{
        background: {tokens.sidebar_bg};
        border-right: 1px solid {tokens.border};
    }}

    /* ---------------------------------------------------------------
       Typography
    --------------------------------------------------------------- */
    QLabel#BrandTitle {{
        color: {tokens.text};
        font-size: 13pt;
        font-weight: 700;
        letter-spacing: 0.5px;
    }}

    QLabel#BrandSubtitle, QLabel#MutedText, QLabel#SectionSubtitle {{
        color: {tokens.muted};
        font-size: 9pt;
    }}

    QLabel#PageTitle {{
        color: {tokens.text};
        font-size: 20pt;
        font-weight: 700;
    }}

    QLabel#SectionTitle {{
        color: {tokens.text};
        font-size: 11pt;
        font-weight: 600;
    }}

    /* Big centred number in an enterprise metric tile */
    QLabel#BigNumber {{
        color: {tokens.text};
        font-size: 36pt;
        font-weight: 800;
        qproperty-alignment: AlignCenter;
    }}

    /* Uppercase caption underneath the big number */
    QLabel#TileLabel {{
        color: {tokens.muted};
        font-size: 8pt;
        font-weight: 600;
        letter-spacing: 1.2px;
        qproperty-alignment: AlignCenter;
    }}

    /* Smaller metric labels used in the summary bar */
    QLabel#SummaryKey {{
        color: {tokens.muted};
        font-size: 9pt;
        font-weight: 600;
        letter-spacing: 0.8px;
    }}

    QLabel#SummaryValue {{
        color: {tokens.text};
        font-size: 14pt;
        font-weight: 700;
    }}

    QLabel#MetricValue {{
        color: {tokens.text};
        font-size: 26pt;
        font-weight: 760;
    }}

    QLabel#MetricCaption, QLabel#SmallLabel {{
        color: {tokens.muted};
        font-size: 9pt;
    }}

    QLabel#HashLabel {{
        color: {tokens.muted};
        font-family: "Cascadia Mono", "Consolas", monospace;
        font-size: 9pt;
    }}

    /* ---------------------------------------------------------------
       Panels — flat / sharp, Rapid7-style
    --------------------------------------------------------------- */

    /* Base panel: zero radius, 1 px border */
    QFrame#GlassPanel, QFrame#MetricTile, QFrame#WorkerCard,
    QFrame#DuplicateGroupCard, QFrame#DuplicateFileRow,
    QFrame#TimelineLane, QFrame#EnterpriseTile {{
        background: {tokens.card_bg};
        border: 1px solid {tokens.border};
        border-radius: 0px;
    }}

    QFrame#MetricTile:hover, QFrame#WorkerCard:hover,
    QFrame#DuplicateGroupCard:hover, QFrame#DuplicateFileRow:hover,
    QFrame#EnterpriseTile:hover {{
        background: {tokens.card_hover};
        border-color: {tokens.primary};
    }}

    /* Hero / scan-bar panel */
    QFrame#HeroPanel {{
        background: {tokens.panel_bg};
        border: 0px;
        border-bottom: 1px solid {tokens.border};
        border-radius: 0px;
    }}

    /* Top summary bar (full-width accent strip) */
    QFrame#EnterpriseBar {{
        background: {tokens.panel_bg};
        border: 0px;
        border-left: 3px solid {tokens.primary};
        border-bottom: 1px solid {tokens.border};
        border-radius: 0px;
    }}

    /* Stat-bar panels (Row 2) */
    QFrame#EnterpriseStatBar {{
        background: {tokens.card_bg};
        border: 1px solid {tokens.border};
        border-radius: 0px;
    }}

    QFrame#GraphPanel, QFrame#DataPanel {{
        background: {tokens.panel_bg};
        border: 1px solid {tokens.border};
        border-radius: 0px;
    }}

    /* Toast notifications */
    QFrame#Toast {{
        background: {tokens.panel_bg};
        border: 1px solid {tokens.border};
        border-radius: 4px;
    }}

    /* Timeline blocks */
    QFrame#TimelineBlock {{
        background: rgba(34, 211, 197, 30);
        border: 1px solid rgba(34, 211, 197, 100);
        border-radius: 2px;
    }}

    QFrame#TimelineBlock[failed="true"] {{
        background: rgba(251, 113, 133, 30);
        border-color: rgba(251, 113, 133, 100);
    }}

    /* ---------------------------------------------------------------
       Sidebar navigation
    --------------------------------------------------------------- */
    QPushButton#NavButton {{
        background: transparent;
        color: {tokens.muted};
        border: 0px;
        border-radius: 0px;
        padding: 10px 16px;
        text-align: left;
        font-size: 10pt;
        font-weight: 500;
    }}

    QPushButton#NavButton:hover {{
        background: {tokens.card_hover};
        color: {tokens.text};
    }}

    QPushButton#NavButton[active="true"] {{
        background: {tokens.card_hover};
        color: {tokens.text};
        border-left: 3px solid {tokens.primary};
        font-weight: 700;
    }}

    /* ---------------------------------------------------------------
       Buttons — flat, 4 px radius
    --------------------------------------------------------------- */
    QPushButton, QToolButton {{
        background: {tokens.primary};
        border: 1px solid {tokens.primary};
        border-radius: 4px;
        color: #000000;
        padding: 7px 16px;
        font-weight: 700;
        font-size: 9pt;
    }}

    QPushButton:hover, QToolButton:hover {{
        background: {tokens.primary_hover};
        border-color: {tokens.primary_hover};
    }}

    QPushButton:disabled {{
        background: {tokens.panel_alt};
        border-color: {tokens.border};
        color: {tokens.faint};
    }}

    QPushButton#SecondaryButton, QToolButton#SecondaryButton {{
        background: {tokens.panel_alt};
        border: 1px solid {tokens.border};
        color: {tokens.text};
    }}

    QPushButton#SecondaryButton:hover, QToolButton#SecondaryButton:hover {{
        background: {tokens.card_hover};
        border-color: {tokens.primary};
        color: {tokens.text};
    }}

    QPushButton#DangerButton {{
        background: rgba(251, 113, 133, 25);
        border: 1px solid rgba(251, 113, 133, 90);
        color: {tokens.danger};
    }}

    QPushButton#DangerButton:hover {{
        background: rgba(251, 113, 133, 50);
        border-color: rgba(251, 113, 133, 140);
    }}

    /* Collapse arrow buttons inside duplicate cards */
    QToolButton#CollapseButton {{
        background: transparent;
        border: 0px;
        color: {tokens.text};
        padding: 5px;
        text-align: left;
        font-weight: 600;
        border-radius: 2px;
    }}

    QToolButton#CollapseButton:hover {{
        background: {tokens.card_hover};
    }}

    /* ---------------------------------------------------------------
       Inputs — flat, 4 px radius
    --------------------------------------------------------------- */
    QLineEdit, QSpinBox {{
        background: {tokens.panel_alt};
        border: 1px solid {tokens.border};
        border-radius: 4px;
        padding: 7px 12px;
        color: {tokens.text};
        selection-background-color: {tokens.primary};
    }}

    QLineEdit:focus, QSpinBox:focus {{
        border: 1px solid {tokens.primary};
    }}

    QCheckBox {{
        color: {tokens.muted};
        spacing: 8px;
    }}

    /* ---------------------------------------------------------------
       Progress bars — flat, 2 px radius
    --------------------------------------------------------------- */
    QProgressBar {{
        background: {tokens.panel_alt};
        border: 0px;
        border-radius: 2px;
        height: 8px;
        text-align: center;
        color: transparent;
    }}

    QProgressBar::chunk {{
        background: {tokens.primary};
        border-radius: 2px;
    }}

    /* ---------------------------------------------------------------
       Tables
    --------------------------------------------------------------- */
    QTableWidget {{
        background: transparent;
        alternate-background-color: {tokens.panel_alt};
        gridline-color: {tokens.border};
        border: 0px;
        color: {tokens.text};
        selection-background-color: {tokens.card_hover};
        selection-color: {tokens.text};
    }}

    QHeaderView::section {{
        background: {tokens.panel_alt};
        color: {tokens.muted};
        border: 0px;
        border-bottom: 1px solid {tokens.border};
        border-right: 1px solid {tokens.border};
        padding: 8px 10px;
        font-size: 8pt;
        font-weight: 700;
        letter-spacing: 0.8px;
    }}

    /* ---------------------------------------------------------------
       Scrollbars — thin, flat
    --------------------------------------------------------------- */
    QScrollBar:vertical {{
        background: transparent;
        width: 6px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background: {tokens.border};
        border-radius: 3px;
        min-height: 20px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: {tokens.faint};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
        background: transparent;
        border: 0px;
        height: 0px;
    }}

    QScrollArea {{
        background: transparent;
        border: 0px;
    }}

    /* ---------------------------------------------------------------
       Dialogs
    --------------------------------------------------------------- */
    QDialog#PremiumDialog {{
        background: {tokens.panel_bg};
        border: 1px solid {tokens.border};
        border-radius: 4px;
        color: {tokens.text};
    }}

    QLabel#DialogTitle {{
        color: {tokens.text};
        font-size: 18pt;
        font-weight: 700;
    }}

    QLabel#DialogBody {{
        color: {tokens.muted};
        font-size: 10pt;
        line-height: 160%;
    }}

    QLabel#DialogMetric {{
        color: {tokens.primary};
        font-size: 22pt;
        font-weight: 800;
    }}
    """


DARK_STYLE = build_style(DARK_TOKENS)
LIGHT_STYLE = build_style(LIGHT_TOKENS)
