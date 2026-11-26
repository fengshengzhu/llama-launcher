"""浅色 / 深色主题：QPalette + QStyleSheet。"""

from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPalette, QPen
from PySide6.QtWidgets import QApplication

DARK = {
    "bg": "#0e121b", "surface": "#171d2a", "surface_alt": "#1e2635",
    "input": "#121824", "border": "#303a4e", "border_soft": "#263042",
    "text": "#e8edf8", "muted": "#929fb8", "faint": "#6c7993",
    "accent": "#7b92ff", "accent_hover": "#93a6ff", "accent_text": "#ffffff",
    "success": "#3fd39c", "danger": "#ff7288", "warning": "#ffc46b",
    "selection": "#33436f", "scroll": "#3a465c",
    "ok_soft": "#16382f", "bad_soft": "#3a1f2b", "warn_soft": "#3a2f19",
    "accent_soft": "#222c4c",
}

LIGHT = {
    "bg": "#f4f6fb", "surface": "#ffffff", "surface_alt": "#f6f8fd",
    "input": "#ffffff", "border": "#d9e0ed", "border_soft": "#e8edf5",
    "text": "#1c2436", "muted": "#6c7891", "faint": "#94a0b5",
    "accent": "#4868e8", "accent_hover": "#3556d6", "accent_text": "#ffffff",
    "success": "#128a62", "danger": "#d13c52", "warning": "#b57a16",
    "selection": "#d7e0ff", "scroll": "#c3cbdb",
    "ok_soft": "#e2f6ee", "bad_soft": "#fde9ed", "warn_soft": "#fcf1dc",
    "accent_soft": "#e9edff",
}

_STYLE = """
QWidget {{
    background: {bg};
    color: {text};
    font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    font-size: 13px;
}}
QFrame#Card {{
    background: {surface};
    border: 1px solid {border_soft};
    border-radius: 12px;
}}
QFrame#CardFlat {{ background: {surface_alt}; border: 1px solid {border_soft}; border-radius: 9px; }}
QFrame#Divider {{ background: {border_soft}; border: none; }}
QFrame#AccentBar {{ background: {accent}; border: none; border-radius: 2px; }}
QWidget#ParamPage {{ background: {surface}; }}

QFrame#AppBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #2b3a86, stop:0.55 #3f5fd8, stop:1 #6a63e8);
    border: none;
    border-radius: 12px;
}}
QFrame#AppBar QLabel {{ color: #ffffff; background: transparent; }}
QFrame#AppBar QLabel#AppTitle {{ font-size: 18px; font-weight: 700; letter-spacing: 0.5px; }}
QFrame#AppBar QLabel#AppSubtitle {{ color: rgba(255,255,255,0.78); font-size: 11px; }}
QFrame#AppBar QLabel#Logo {{
    background: rgba(255,255,255,0.20);
    border: 1px solid rgba(255,255,255,0.32);
    border-radius: 10px;
    font-size: 17px; font-weight: 800;
    min-width: 38px; max-width: 38px; min-height: 38px; max-height: 38px;
    qproperty-alignment: AlignCenter;
}}
QFrame#AppBar QPushButton {{
    background: rgba(255,255,255,0.13);
    color: #ffffff;
    border: 1px solid rgba(255,255,255,0.22);
    border-radius: 7px;
    padding: 6px 12px;
}}
QFrame#AppBar QPushButton:hover {{ background: rgba(255,255,255,0.24); }}
QFrame#AppBar QLabel#StatusPill {{
    background: rgba(255,255,255,0.16);
    border: 1px solid rgba(255,255,255,0.28);
    border-radius: 20px;
    padding: 5px 13px;
    font-size: 12px;
    font-weight: 600;
}}

QLabel#AppTitle {{ font-size: 19px; font-weight: 700; letter-spacing: 0.3px; }}
QLabel#AppSubtitle {{ color: {muted}; font-size: 12px; }}
QLabel#SectionTitle {{ font-size: 14px; font-weight: 700; }}
QLabel#GroupLabel {{ color: {faint}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel#Muted {{ color: {muted}; }}
QLabel#Hint {{ color: {muted}; font-size: 12px; }}
QLabel#Faint {{ color: {faint}; font-size: 11px; }}
QLabel#StatusOk {{ color: {success}; font-weight: 600; }}
QLabel#StatusBad {{ color: {danger}; font-weight: 600; }}
QLabel#EnvKey {{ color: {faint}; font-size: 11px; }}
QLabel#EnvValue {{ color: {text}; font-size: 12px; }}
QLabel#UrlLabel {{ color: {accent}; font-size: 12px; font-weight: 600; }}
QLabel#Warning {{ color: {danger}; font-size: 12px; }}
QLabel#Badge {{
    background: {accent_soft}; color: {accent};
    border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: 600;
}}
QLabel#BadgeOk {{ background: {ok_soft}; color: {success}; border-radius: 4px; padding: 2px 7px; font-size: 11px; font-weight: 600; }}
QLabel#BadgeMuted {{ background: {surface_alt}; color: {muted}; border-radius: 4px; padding: 2px 7px; font-size: 11px; }}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background: {input};
    color: {text};
    border: 1px solid {border};
    border-radius: 7px;
    padding: 6px 10px;
    selection-background-color: {selection};
    selection-color: {text};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus {{ border: 1px solid {accent}; }}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled, QPlainTextEdit:disabled {{ color: {muted}; background: {surface_alt}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: transparent; border: none; width: 17px;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-bottom: 5px solid {muted}; margin-bottom: 3px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {muted}; margin-top: 3px;
}}
QComboBox {{ padding: 6px 9px; min-height: 20px; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox::down-arrow {{
    image: none; border-left: 4px solid transparent; border-right: 4px solid transparent;
    border-top: 5px solid {muted}; margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background: {surface}; color: {text}; border: 1px solid {border};
    border-radius: 7px; padding: 4px;
    selection-background-color: {selection}; selection-color: {text};
}}

QPushButton {{
    background: {surface_alt}; color: {text};
    border: 1px solid {border}; border-radius: 7px;
    padding: 7px 14px; min-height: 19px;
}}
QPushButton:hover {{ background: {selection}; border-color: {accent}; }}
QPushButton:pressed {{ background: {accent_soft}; }}
QPushButton:disabled {{ color: {faint}; background: {surface_alt}; border-color: {border_soft}; }}
QPushButton[variant="primary"] {{
    background: {accent}; color: {accent_text}; border: 1px solid {accent};
    font-weight: 700; padding: 9px 22px; font-size: 13px;
}}
QPushButton[variant="primary"]:hover {{ background: {accent_hover}; border-color: {accent_hover}; }}
QPushButton[variant="primary"]:disabled {{ background: {border}; border-color: {border}; color: {faint}; }}
QPushButton[variant="danger"] {{ background: {bad_soft}; color: {danger}; border: 1px solid {danger}; }}
QPushButton[variant="danger"]:hover {{ background: {danger}; color: {surface}; }}
QPushButton[variant="ghost"] {{ background: transparent; border: 1px solid transparent; color: {muted}; }}
QPushButton[variant="ghost"]:hover {{ background: {surface_alt}; color: {text}; }}
QPushButton[variant="flat"] {{ background: {surface_alt}; border: 1px solid {border_soft}; padding: 5px 9px; }}
QPushButton[variant="flat"]:hover {{ border-color: {accent}; }}

QCheckBox {{ background: transparent; spacing: 7px; }}
QCheckBox::indicator {{
    width: 17px; height: 17px;
    border: 1px solid {border}; border-radius: 5px; background: {input};
}}
QCheckBox::indicator:hover {{ border-color: {accent}; }}
QCheckBox::indicator:checked {{
    background: {accent}; border-color: {accent};
    image: url("{check_icon}");
}}
QCheckBox::indicator:disabled {{ background: {surface_alt}; border-color: {border_soft}; }}
QCheckBox:disabled {{ color: {muted}; }}

QWidget#ParamRow[active="false"] QLabel#ParamLabel {{ color: {faint}; }}
QWidget#ParamRow[active="false"] QLineEdit,
QWidget#ParamRow[active="false"] QSpinBox,
QWidget#ParamRow[active="false"] QDoubleSpinBox,
QWidget#ParamRow[active="false"] QComboBox {{ color: {muted}; }}
QWidget#ParamRow:hover {{ background: {surface_alt}; border-radius: 7px; }}
QLabel#ParamFlag {{ color: {faint}; font-size: 11px; }}

QTabWidget::pane {{
    background: {surface}; border: 1px solid {border_soft};
    border-radius: 9px; top: -1px;
}}
QTabBar::tab {{
    background: transparent; color: {muted};
    border: 1px solid transparent; border-bottom: 2px solid transparent;
    border-radius: 0px; padding: 8px 15px; margin-right: 2px;
}}
QTabBar::tab:hover {{ color: {text}; background: {surface_alt}; }}
QTabBar::tab:selected {{
    color: {accent}; border-bottom: 2px solid {accent}; font-weight: 700;
}}

QListWidget {{
    background: {input}; border: 1px solid {border};
    border-radius: 8px; padding: 5px;
}}
QListWidget::item {{ border-radius: 6px; padding: 9px 8px; border-left: 3px solid transparent; }}
QListWidget::item:hover {{ background: {surface_alt}; }}
QListWidget::item:selected {{
    background: {accent_soft}; color: {text}; border-left: 3px solid {accent};
}}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar:horizontal {{ background: transparent; height: 9px; margin: 2px; }}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
    background: {scroll}; border-radius: 4px; min-height: 26px; min-width: 26px;
}}
QScrollBar::handle:hover {{ background: {muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ border: none; background: transparent; width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{
    background: {surface_alt}; color: {text};
    border: 1px solid {border}; border-radius: 6px; padding: 6px 8px;
}}
QMessageBox {{ background: {surface}; color: {text}; }}
QSplitter::handle {{ background: transparent; }}
QSplitter::handle:horizontal {{ width: 6px; }}
QSplitter::handle:vertical {{ height: 6px; }}
"""


def _check_icon_path() -> str:
    """生成白色对勾小图标，让复选框选中态有明确标识。"""
    path = os.path.join(tempfile.gettempdir(), "llama-launcher-check.png")
    try:
        image = QImage(16, 16, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(QColor("#ffffff"))
        pen.setWidthF(2.2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawLine(3, 8, 7, 12)
        painter.drawLine(7, 12, 13, 4)
        painter.end()
        image.save(path, "PNG")
        return path.replace("\\", "/")
    except Exception:
        return ""


def _system_is_dark() -> bool:
    try:
        hints = QApplication.instance().styleHints()
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except (AttributeError, RuntimeError):
        pass
    palette = QApplication.instance().palette()
    return palette.color(QPalette.ColorRole.Window).lightness() < 128


class ThemeManager(QObject):
    mode_changed = Signal(str)
    palette_changed = Signal(bool)

    def __init__(self, app: QApplication, mode: str = "system") -> None:
        super().__init__(app)
        self.app = app
        self.mode = mode if mode in {"system", "light", "dark"} else "system"
        self.colors = LIGHT
        self.is_dark = False
        self.check_icon = _check_icon_path()

    def apply(self, mode: str | None = None) -> None:
        if mode is not None:
            self.mode = mode if mode in {"system", "light", "dark"} else "system"
        self.is_dark = self.mode == "dark" or (self.mode == "system" and _system_is_dark())
        self.colors = DARK if self.is_dark else LIGHT
        self.app.setStyle("Fusion")
        self.app.setPalette(self._build_palette())
        tokens = dict(self.colors)
        tokens["check_icon"] = self.check_icon
        stylesheet = _STYLE.format(**tokens)
        if not self.check_icon:
            stylesheet = stylesheet.replace('image: url("");', "image: none;")
        self.app.setStyleSheet(stylesheet)
        self.mode_changed.emit(self.mode)
        self.palette_changed.emit(self.is_dark)

    def _build_palette(self) -> QPalette:
        c = self.colors
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(c["bg"]))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(c["text"]))
        palette.setColor(QPalette.ColorRole.Base, QColor(c["input"]))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(c["surface_alt"]))
        palette.setColor(QPalette.ColorRole.Text, QColor(c["text"]))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(c["surface_alt"]))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(c["text"]))
        palette.setColor(QPalette.ColorRole.Button, QColor(c["surface_alt"]))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(c["text"]))
        palette.setColor(QPalette.ColorRole.Link, QColor(c["accent"]))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(c["selection"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(c["text"]))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(c["muted"]))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(c["muted"]))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(c["muted"]))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(c["muted"]))
        return palette
