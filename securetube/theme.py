from __future__ import annotations

from string import Template
from typing import Callable, List, Optional

from PySide6.QtGui import QFont, QFontDatabase

from . import winutil
from .extensions import BUILTIN, Accent, Theme, lum, mix, with_accent


def flags(*fl) -> int:
    """Склейка флагов Qt в int (безопасно даже для флагов из разных enum)."""
    r = 0
    for f in fl:
        r |= int(getattr(f, "value", f))
    return r

C: dict = dict(BUILTIN.colors)          
R: dict = {}                              
IS_DARK = True
_listeners: List[Callable[[], None]] = []


def _radii(r: int) -> dict:
    return {"card": r, "btn": round(r * .72), "input": round(r * .86), "frame": r + 2 if r else 0,
            "seg": round(r * .57), "chip": round(r * .68), "round": 20 if r else 0, "play": 22 if r else 0}


R.update(_radii(BUILTIN.radius))


def on_change(fn: Callable[[], None]) -> None:
    """Подписка на смену темы (перекрасить иконки, перерисовать)."""
    _listeners.append(fn)


def apply(theme: Theme, accent: Optional[Accent] = None) -> None:
    """Применяет тему и (необязательно) свой акцент ко всему приложению."""
    global IS_DARK
    colors = dict(theme.colors)
    if accent is not None:
        colors = with_accent(colors, accent.accent, accent.accent2)
    C.update(colors)
    R.clear()
    R.update(_radii(theme.radius))
    IS_DARK = lum(C["bg"]) < 0.3
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(build_qss())
    for fn in list(_listeners):
        fn()


def decorate(hwnd: int) -> None:
    """Заголовок окна под цвет темы (Windows)."""
    winutil.dark_titlebar(hwnd, C["panel"], C["text"], IS_DARK)


_FAMILIES = ("Segoe UI Variable Text", "Segoe UI", "Inter", "SF Pro Text", "Noto Sans", "Arial")
_family = "Segoe UI"


def pick_family() -> str:
    global _family
    have = set(QFontDatabase.families())
    for f in _FAMILIES:
        if f in have:
            _family = f
            break
    return _family


def font(px: int = 14, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(_family)
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


_QSS = Template("""
* { outline: 0; }
QWidget { background: transparent; color: $text; font-family: "$family"; font-size: 14px; }
QMainWindow, QDialog, QMessageBox { background: $bg; }
QToolTip { background: $raised; color: $text; border: 1px solid $line2; padding: 6px 10px; border-radius: ${r_seg}px; }
QLabel#h1 { font-size: 24px; font-weight: 700; }
QLabel#h2 { font-size: 17px; font-weight: 650; }
QLabel#muted { color: $muted; font-size: 13px; }
QLabel#error { color: $danger; }
QLabel#ok { color: $ok; }

QLineEdit { background: $panel; border: 1px solid $line; border-radius: ${r_input}px; padding: 0 14px;
            min-height: 40px; selection-background-color: $accent; }
QLineEdit:hover { border-color: $line2; }
QLineEdit:focus { border: 1px solid $accent2; }
QLineEdit:disabled { color: $dim; }

QPushButton { background: $raised; border: 1px solid $line; border-radius: ${r_btn}px; padding: 8px 16px; }
QPushButton:hover { background: $hover; border-color: $line2; }
QPushButton:pressed { background: $line; }
QPushButton:disabled { color: $dim; background: $panel; }
QPushButton:focus { border-color: $accent2; }
QPushButton#primary { background: $accent; border: 0; color: $on_accent; font-weight: 600; padding: 9px 18px; }
QPushButton#primary:hover { background: $accent_hi; }
QPushButton#primary:pressed { background: $accent; }
QPushButton#primary:disabled { background: $line2; color: $muted; }
QPushButton#ghost { background: transparent; border: 0; color: $muted; }
QPushButton#ghost:hover { background: $hover; color: $text; }
QPushButton#icon { background: transparent; border: 0; border-radius: ${r_round}px; padding: 0; }
QPushButton#icon:hover { background: $hover; }
QPushButton#icon:pressed { background: $line; }
QPushButton#play { background: $accent; border: 0; border-radius: ${r_play}px; padding: 0; }
QPushButton#play:hover { background: $accent_hi; }
QPushButton#danger { color: $danger; }
QPushButton#danger:hover { background: $danger_bg; border-color: $danger_bd; }
QPushButton#seg { background: transparent; border: 0; border-radius: ${r_seg}px; padding: 6px 14px; color: $muted; }
QPushButton#seg:hover { color: $text; }
QPushButton#seg:checked { background: $hover; color: $text; }
QFrame#segbox { background: $panel; border: 1px solid $line; border-radius: ${r_btn}px; }
QFrame#card { background: $panel; border: 1px solid $line; border-radius: ${r_frame}px; }
QFrame#rowline { background: $line; max-height: 1px; min-height: 1px; border: 0; }

QScrollArea { border: 0; background: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: $line2; border-radius: ${r_pb}px; min-height: 48px; }
QScrollBar::handle:vertical:hover { background: $dim; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }

QListView { background: transparent; border: 0; }

QMenu { background: $raised; border: 1px solid $line2; padding: 6px; }
QMenu::item { padding: 8px 28px 8px 14px; border-radius: ${r_seg}px; margin: 1px 0; }
QMenu::item:selected { background: $hover; }
QMenu::item:disabled { color: $dim; }
QMenu::separator { height: 1px; background: $line; margin: 6px 8px; }
QMenu::indicator { width: 14px; height: 14px; margin-left: 6px; }

QProgressBar { background: $line; border: 0; border-radius: ${r_pb}px; max-height: 4px; min-height: 4px; }
QProgressBar::chunk { background: $accent; border-radius: ${r_pb}px; }
""")


def build_qss() -> str:
    extra = {"danger_bg": mix(C["bg"], C["danger"], .16), "danger_bd": mix(C["bg"], C["danger"], .4),
             "r_input": R["input"], "r_btn": R["btn"], "r_round": R["round"], "r_play": R["play"],
             "r_seg": R["seg"], "r_frame": R["frame"], "r_pb": 2 if R["card"] else 0}
    return _QSS.substitute(family=_family, **C, **extra)
