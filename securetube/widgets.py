from __future__ import annotations

import weakref
from typing import Callable, List, Optional, Tuple

from PySide6.QtCore import (QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QRectF,
                            QSize, Qt, QTimer, QVariantAnimation, Signal)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QFrame, QHBoxLayout, QPushButton,
                               QSlider, QToolTip, QVBoxLayout, QWidget)

from . import theme, winutil
from .icons import icon
from .theme import C, R, flags, font


_TRACKED: list = []


def icon_button(name: str, tip: str = "", size: int = 40, icon_px: int = 22,
                color: Optional[str] = None, obj: str = "icon", track: bool = True) -> QPushButton:
    b = QPushButton()
    b.setObjectName(obj)
    b.setIcon(icon(name, color or C["text"], icon_px))
    if track:                       # иконка перекрашивается при смене темы
        _TRACKED.append((weakref.ref(b), name, color, icon_px))
    b.setIconSize(QSize(icon_px, icon_px))
    b.setFixedSize(size, size)
    b.setToolTip(tip)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    return b


def refresh_icon_buttons() -> None:
    alive = []
    for ref, name, color, px in _TRACKED:
        b = ref()
        if b is not None:
            b.setIcon(icon(name, color or C["text"], px))
            alive.append((ref, name, color, px))
    _TRACKED[:] = alive


theme.on_change(refresh_icon_buttons)


def hline() -> QFrame:
    f = QFrame()
    f.setObjectName("rowline")
    f.setFixedHeight(1)
    return f


class ClickSlider(QSlider):
    """Слайдер: клик перемещает ползунок в точку клика, при наведении утолщается."""

    def __init__(self, thick: int = 4, tip: Optional[Callable[[int], str]] = None):
        super().__init__(Qt.Orientation.Horizontal)
        self._thick, self._tip = thick, tip
        self._h = 0.0
        self.setMouseTracking(True)
        self.setFixedHeight(22)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(130)
        self._anim.valueChanged.connect(self._set_h)

    def _set_h(self, v):
        self._h = float(v)
        self.update()

    def _go(self, target: float):
        self._anim.stop()
        self._anim.setStartValue(self._h)
        self._anim.setEndValue(target)
        self._anim.start()

    def _pad(self) -> int:
        return 8

    def _value_at(self, x: float) -> int:
        w = max(1, self.width() - 2 * self._pad())
        ratio = min(1.0, max(0.0, (x - self._pad()) / w))
        return self.minimum() + round(ratio * (self.maximum() - self.minimum()))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.setSliderDown(True)
            self.setSliderPosition(self._value_at(e.position().x()))
            e.accept()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        v = self._value_at(e.position().x())
        if self.isSliderDown():
            self.setSliderPosition(v)
        if self._tip:
            QToolTip.showText(self.mapToGlobal(QPoint(int(e.position().x()) - 18, -34)), self._tip(v), self)
        e.accept()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.isSliderDown():
            self.setSliderPosition(self._value_at(e.position().x()))
            self.setSliderDown(False)
            e.accept()
        else:
            super().mouseReleaseEvent(e)

    def wheelEvent(self, e):
        e.ignore()

    def enterEvent(self, e):
        self._go(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._go(0.0)
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pad = self._pad()
        w = self.width() - 2 * pad
        cy = self.height() / 2
        th = self._thick + 2 * self._h
        span = self.maximum() - self.minimum()
        ratio = (self.sliderPosition() - self.minimum()) / span if span > 0 else 0.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(C["line2"]))
        p.drawRoundedRect(QRectF(pad, cy - th / 2, w, th), th / 2, th / 2)
        p.setBrush(QColor(C["accent"]))
        p.drawRoundedRect(QRectF(pad, cy - th / 2, max(0.0, w * ratio), th), th / 2, th / 2)
        if self._h > 0.01 or self.isSliderDown():
            r = 6.5 * max(self._h, 1.0 if self.isSliderDown() else 0.0)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(pad + w * ratio, cy), r, r)


class Switch(QAbstractButton):
    def __init__(self, checked: bool = False):
        super().__init__()
        self.setCheckable(True)
        self.setFixedSize(46, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._pos = 1.0 if checked else 0.0
        super().setChecked(checked)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._tick)
        self.clicked.connect(self._on_click)

    def setChecked(self, on: bool):                      
        super().setChecked(on)
        self._pos = 1.0 if on else 0.0
        self.update()

    def _tick(self, v):
        self._pos = float(v)
        self.update()

    def _on_click(self):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if self.isChecked() else 0.0)
        self._anim.start()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        off, on = QColor(C["line2"]), QColor(C["accent"])
        t = self._pos
        col = QColor(int(off.red() + (on.red() - off.red()) * t),
                     int(off.green() + (on.green() - off.green()) * t),
                     int(off.blue() + (on.blue() - off.blue()) * t))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        p.drawRoundedRect(QRectF(0, 1, 46, 24), 12, 12)
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(13 + 20 * t, 13), 9, 9)


class Segmented(QFrame):
    changed = Signal(object)

    def __init__(self, options: List[Tuple[object, str]]):
        super().__init__()
        self.setObjectName("segbox")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._values: List[object] = []
        for i, (val, label) in enumerate(options):
            b = QPushButton(label)
            b.setObjectName("seg")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            self._group.addButton(b, i)
            self._values.append(val)
            lay.addWidget(b)
        self._group.idClicked.connect(lambda i: self.changed.emit(self._values[i]))

    def value(self):
        i = self._group.checkedId()
        return self._values[i] if i >= 0 else None

    def setValue(self, v):
        if v in self._values:
            self._group.button(self._values.index(v)).setChecked(True)


class NavItem(QAbstractButton):
    def __init__(self, key: str, icon_name: str, text: str, count: Optional[int] = None):
        super().__init__()
        self.key, self._icon, self._text, self._count = key, icon_name, text, count
        self.compact = False
        self.setCheckable(True)
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(text)

    def set_text(self, text: str):
        self._text = text
        self.setToolTip(text)
        self.update()

    def set_count(self, n: Optional[int]):
        self._count = n
        self.update()

    def set_compact(self, on: bool):
        self.compact = on
        self.update()

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(8, 2, -8, -2)
        checked = self.isChecked()
        p.setPen(Qt.PenStyle.NoPen)
        if checked or self.underMouse():
            p.setBrush(QColor(C["raised"] if checked else C["hover"]))
            p.drawRoundedRect(r, R["btn"], R["btn"])
        if checked:
            p.setBrush(QColor(C["accent"]))
            p.drawRoundedRect(QRectF(r.left() + 1, r.center().y() - 9, 3, 18), 1.5, 1.5)
        ic = icon(self._icon, C["text"] if checked else C["muted"], 20)
        if self.compact:
            ic.paint(p, QRect(int(r.center().x() - 10), int(r.center().y() - 10), 20, 20))
            return
        ic.paint(p, QRect(int(r.left() + 16), int(r.center().y() - 10), 20, 20))
        p.setFont(font(14, QFont.Weight.DemiBold if checked else QFont.Weight.Normal))
        p.setPen(QColor(C["text"] if checked else C["muted"]))
        right = r.right() - 12
        if self._count is not None:
            cnt = str(self._count)
            p.setFont(font(12))
            cw = QFontMetrics(p.font()).horizontalAdvance(cnt)
            p.setPen(QColor(C["dim"]))
            p.drawText(QRectF(right - cw, r.top(), cw, r.height()), flags(Qt.AlignmentFlag.AlignVCenter, Qt.AlignmentFlag.AlignRight), cnt)
            right -= cw + 8
            p.setFont(font(14, QFont.Weight.DemiBold if checked else QFont.Weight.Normal))
            p.setPen(QColor(C["text"] if checked else C["muted"]))
        left = r.left() + 48
        txt = QFontMetrics(p.font()).elidedText(self._text, Qt.TextElideMode.ElideRight, int(right - left))
        p.drawText(QRectF(left, r.top(), right - left, r.height()), flags(Qt.AlignmentFlag.AlignVCenter, Qt.AlignmentFlag.AlignLeft), txt)


def _translucent_toplevel(w: QWidget):
    w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    w.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)


class Toast(QWidget):
    """Всплывающее сообщение поверх всего, в том числе поверх видео."""

    def __init__(self, host: QWidget):
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        _translucent_toplevel(self)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.host, self.kind, self.text = host, "info", ""
        self.capture_hidden = False
        self.lift = 96
        self._fading = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.finished.connect(self._after)

    def show_message(self, text: str, kind: str = "info", ms: int = 0):
        self.text, self.kind = text, kind
        fm = QFontMetrics(font(14))
        box = fm.boundingRect(QRect(0, 0, 460, 400), flags(Qt.TextFlag.TextWordWrap), text)
        self.resize(box.width() + 70, box.height() + 28)
        g = self.host.frameGeometry()
        self.move(g.center().x() - self.width() // 2, g.bottom() - self.height() - self.lift)
        self._fading = False
        self._anim.stop()
        self.setWindowOpacity(0.0)
        self.show()
        winutil.capture_hidden(int(self.winId()), self.capture_hidden)
        self._anim.setDuration(160)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(ms or (6000 if kind == "error" else 3200))

    def _fade_out(self):
        self._fading = True
        self._anim.stop()
        self._anim.setDuration(260)
        self._anim.setStartValue(self.windowOpacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _after(self):
        if self._fading:
            self._fading = False
            self.hide()

    def hide_now(self):
        self._timer.stop()
        self._anim.stop()
        self.hide()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(C["line2"]), 1))
        p.setBrush(QColor(C["raised"]))
        p.drawRoundedRect(r, R["btn"] + 4, R["btn"] + 4)
        dot = {"error": C["danger"], "ok": C["ok"]}.get(self.kind, C["accent2"])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(dot))
        p.drawEllipse(QPointF(26, r.center().y()), 5, 5)
        p.setPen(QColor(C["text"]))
        p.setFont(font(14))
        p.drawText(QRectF(46, 0, self.width() - 62, self.height()),
                   flags(Qt.AlignmentFlag.AlignVCenter, Qt.AlignmentFlag.AlignLeft, Qt.TextFlag.TextWordWrap), self.text)


class FloatingHost(QWidget):
    """Окно-подложка для панели управления в полноэкранном режиме.

    Отдельное окно верхнего уровня всегда рисуется поверх видео,
    независимо от того, как видеобэкенд выводит картинку.
    """

    def __init__(self):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        _translucent_toplevel(self)
        self.capture_hidden = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 8)
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.finished.connect(self._after)
        self._hiding = False

    def attach(self, w: QWidget):
        self.layout().addWidget(w)
        w.show()

    def detach(self, w: QWidget):
        self.layout().removeWidget(w)
        w.setParent(None)

    def reveal(self, screen_rect: QRect):
        width = min(1100, screen_rect.width() - 96)
        self.setFixedWidth(width)
        self.adjustSize()
        self.move(screen_rect.left() + (screen_rect.width() - width) // 2,
                  screen_rect.bottom() - self.height() - 36)
        self._hiding = False
        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.show()
            winutil.capture_hidden(int(self.winId()), self.capture_hidden)
        self._anim.stop()
        self._anim.setDuration(140)
        self._anim.setStartValue(self.windowOpacity())
        self._anim.setEndValue(1.0)
        self._anim.start()

    def conceal(self):
        if not self.isVisible():
            return
        self._hiding = True
        self._anim.stop()
        self._anim.setDuration(240)
        self._anim.setStartValue(self.windowOpacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _after(self):
        if self._hiding:
            self._hiding = False
            self.hide()

    def hide_now(self):
        self._anim.stop()
        self._hiding = False
        self.hide()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(255, 255, 255, 28), 1))
        bg = QColor(C["bg"])
        bg.setAlpha(225)
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(self.rect()).adjusted(1, 1, -1, -1), R["card"] + 4, R["card"] + 4)
