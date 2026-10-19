from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QGuiApplication, QIcon, QLinearGradient, QPainter,
                           QPen, QPixmap, QBrush, QPolygonF)

from . import theme
from .theme import C

_cache: dict = {}
theme.on_change(lambda: _cache.clear())


def _pt(x, y):
    return QPointF(x, y)


def _line(p, *pts):
    p.drawPolyline(QPolygonF([_pt(x, y) for x, y in pts]))


def _fill_poly(p, *pts):
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(QPolygonF([_pt(x, y) for x, y in pts]))


def _star(fill: bool):
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        r = 9.6 if i % 2 == 0 else 4.2
        pts.append((12 + r * math.cos(a), 12.8 + r * math.sin(a)))
    return pts


def _speaker(p):
    p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(QPolygonF([_pt(3.5, 9), _pt(7.5, 9), _pt(12.5, 4.8), _pt(12.5, 19.2), _pt(7.5, 15), _pt(3.5, 15)]))


def _d_play(p):    p.setPen(Qt.PenStyle.NoPen); p.drawPolygon(QPolygonF([_pt(7.5, 4.5), _pt(19.5, 12), _pt(7.5, 19.5)]))
def _d_pause(p):   p.setPen(Qt.PenStyle.NoPen); p.drawRoundedRect(QRectF(6.5, 4.5, 4, 15), 1.2, 1.2); p.drawRoundedRect(QRectF(13.5, 4.5, 4, 15), 1.2, 1.2)
def _d_prev(p):    _fill_poly(p, (19, 5), (9, 12), (19, 19)); p.setPen(_pen(p)); _line(p, (5.5, 5), (5.5, 19))
def _d_next(p):    _fill_poly(p, (5, 5), (15, 12), (5, 19)); p.setPen(_pen(p)); _line(p, (18.5, 5), (18.5, 19))
def _d_volume(p):
    _speaker(p); p.setPen(_pen(p)); p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(QRectF(8, 7.5, 9, 9), -55 * 16, 110 * 16); p.drawArc(QRectF(7, 3.5, 15, 17), -55 * 16, 110 * 16)
def _d_mute(p):
    _speaker(p); p.setPen(_pen(p)); _line(p, (16, 9.5), (21, 14.5)); _line(p, (21, 9.5), (16, 14.5))
def _d_full(p):
    _line(p, (4, 9), (4, 4), (9, 4)); _line(p, (15, 4), (20, 4), (20, 9)); _line(p, (20, 15), (20, 20), (15, 20)); _line(p, (9, 20), (4, 20), (4, 15))
def _d_unfull(p):
    _line(p, (9, 4), (9, 9), (4, 9)); _line(p, (15, 4), (15, 9), (20, 9)); _line(p, (20, 15), (15, 15), (15, 20)); _line(p, (4, 15), (9, 15), (9, 20))
def _d_plus(p):    _line(p, (12, 5), (12, 19)); _line(p, (5, 12), (19, 12))
def _d_search(p):  p.drawEllipse(_pt(10.5, 10.5), 6.2, 6.2); _line(p, (15.3, 15.3), (20, 20))
def _d_grid(p):
    for x, y in ((4, 4), (13.5, 4), (4, 13.5), (13.5, 13.5)):
        p.drawRoundedRect(QRectF(x, y, 6.5, 6.5), 1.8, 1.8)
def _d_star(p):    p.drawPolygon(QPolygonF([_pt(*q) for q in _star(False)]))
def _d_star_f(p):  p.setBrush(p.pen().color()); p.drawPolygon(QPolygonF([_pt(*q) for q in _star(True)]))
def _d_gear(p):
    p.drawEllipse(_pt(12, 12), 6.3, 6.3); p.drawEllipse(_pt(12, 12), 2.4, 2.4)
    for i in range(8):
        a = i * math.pi / 4; _line(p, (12 + 6.3 * math.cos(a), 12 + 6.3 * math.sin(a)), (12 + 9.3 * math.cos(a), 12 + 9.3 * math.sin(a)))
def _d_lock(p):
    p.drawRoundedRect(QRectF(5.5, 10.5, 13, 9.5), 2.5, 2.5); p.drawArc(QRectF(8, 3.5, 8, 14), 0, 180 * 16)
def _d_back(p):    _line(p, (19, 12), (5, 12)); _line(p, (11, 6), (5, 12), (11, 18))
def _d_trash(p):
    _line(p, (4.5, 7), (19.5, 7)); _line(p, (9.5, 7), (9.5, 4.5), (14.5, 4.5), (14.5, 7))
    p.drawRoundedRect(QRectF(6.5, 7, 11, 13), 2, 2)
def _d_folder_plus(p):
    _line(p, (3.5, 18.5), (3.5, 6.5), (9.5, 6.5), (11.5, 9), (20.5, 9), (20.5, 18.5), (3.5, 18.5)); _line(p, (12, 12), (12, 16)); _line(p, (10, 14), (14, 14))
def _d_tag(p):
    _line(p, (3.5, 4.5), (11.5, 4.5), (20.5, 13.5), (13.5, 20.5), (3.5, 10.5), (3.5, 4.5)); p.drawEllipse(_pt(8, 9), 1.3, 1.3)
def _d_list(p):
    for y in (7, 12, 17):
        _line(p, (9.5, y), (20, y)); p.drawPoint(_pt(5, y))
def _d_menu(p):    _line(p, (4, 6.5), (20, 6.5)); _line(p, (4, 12), (20, 12)); _line(p, (4, 17.5), (20, 17.5))
def _d_sort(p):
    _line(p, (8, 5), (8, 19)); _line(p, (5, 16), (8, 19), (11, 16)); _line(p, (16, 19), (16, 5)); _line(p, (13, 8), (16, 5), (19, 8))
def _d_close(p):   _line(p, (6, 6), (18, 18)); _line(p, (18, 6), (6, 18))
def _d_check(p):   _line(p, (5, 12.5), (10, 17.5), (19, 7))
def _d_speed(p):   p.drawArc(QRectF(3.5, 5, 17, 17), 0, 180 * 16); _line(p, (12, 14.5), (16.5, 9.5)); p.drawPoint(_pt(12, 14.5))
def _d_dots(p):
    p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(p.brush().color()))
    for y in (5.5, 12, 18.5):
        p.drawEllipse(_pt(12, y), 1.8, 1.8)
def _d_edit(p):    _line(p, (4.5, 19.5), (5.5, 15), (16, 4.5), (19.5, 8), (9, 18.5), (4.5, 19.5))
def _d_palette(p):
    p.drawEllipse(_pt(12, 12), 9, 9)
    for x, y in ((8, 10), (12, 7.5), (16, 10), (7.5, 14.5)):
        p.drawPoint(_pt(x, y))


def _d_globe(p):
    p.drawEllipse(_pt(12, 12), 9, 9)
    p.drawEllipse(_pt(12, 12), 4, 9)
    _line(p, (3, 12), (21, 12))
    _line(p, (5, 7.5), (19, 7.5))
    _line(p, (5, 16.5), (19, 16.5))
def _d_forward(p):  _line(p, (5, 12), (19, 12)); _line(p, (13, 6), (19, 12), (13, 18))
def _d_reload(p):
    p.drawArc(QRectF(5, 5, 14, 14), 50 * 16, 285 * 16)
    _line(p, (19.5, 4.5), (15.2, 6.4), (17.2, 10.6))
def _d_home(p):
    _line(p, (4, 11.5), (12, 4.5), (20, 11.5))
    _line(p, (6.5, 10), (6.5, 19.5), (17.5, 19.5), (17.5, 10))
    _line(p, (10, 19.5), (10, 14.5), (14, 14.5), (14, 19.5))
def _d_shield(p):
    _line(p, (12, 3), (19, 5.8), (19, 12), (12, 21), (5, 12), (5, 5.8), (12, 3))
    _line(p, (8.6, 12), (11, 14.4), (15.4, 9.6))
def _d_external(p):
    _line(p, (14, 4), (20, 4), (20, 10))
    _line(p, (20, 4), (11, 13))
    _line(p, (18, 14), (18, 19), (5, 19), (5, 6), (10, 6))


def _d_film(p):
    p.drawRoundedRect(QRectF(3.5, 5, 17, 14), 3, 3); p.setBrush(p.pen().color()); p.setPen(Qt.PenStyle.NoPen)
    p.drawPolygon(QPolygonF([_pt(10.2, 9), _pt(15, 12), _pt(10.2, 15)]))


_PEN = None


def _pen(p):
    return _PEN


_DRAW = {
    "play": _d_play, "pause": _d_pause, "prev": _d_prev, "next": _d_next, "volume": _d_volume,
    "mute": _d_mute, "full": _d_full, "unfull": _d_unfull, "plus": _d_plus, "search": _d_search,
    "grid": _d_grid, "star": _d_star, "star_f": _d_star_f, "gear": _d_gear, "lock": _d_lock,
    "back": _d_back, "trash": _d_trash, "folder_plus": _d_folder_plus, "tag": _d_tag, "list": _d_list,
    "menu": _d_menu, "sort": _d_sort, "close": _d_close, "check": _d_check, "speed": _d_speed,
    "dots": _d_dots, "edit": _d_edit, "film": _d_film, "palette": _d_palette, "globe": _d_globe, "forward": _d_forward,
    "reload": _d_reload, "home": _d_home, "shield": _d_shield, "external": _d_external,
}
_FILLED = {"play", "pause", "prev", "next", "volume", "mute", "star_f", "dots"}


def icon(name: str, color: str | None = None, size: int = 22) -> QIcon:
    color = color or C["text"]
    dpr = max(1.0, QGuiApplication.primaryScreen().devicePixelRatio()) if QGuiApplication.primaryScreen() else 1.0
    key = (name, color, size, dpr)
    if key in _cache:
        return _cache[key]
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 24.0, size / 24.0)
    col = QColor(color)
    pen = QPen(col, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    global _PEN
    _PEN = pen
    p.setPen(pen)
    p.setBrush(QBrush(col) if name in _FILLED else Qt.BrushStyle.NoBrush)
    _DRAW[name](p)
    p.end()
    ic = QIcon(px)
    _cache[key] = ic
    return ic


def paint_logo(p: QPainter, r: QRectF) -> None:
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0.0, QColor(C["accent"]))
    g.setColorAt(1.0, QColor(C["accent2"]))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(g))
    p.drawRoundedRect(r, r.width() * 0.27, r.width() * 0.27)
    w, h = r.width(), r.height()
    tri = QPolygonF([QPointF(r.left() + w * 0.39, r.top() + h * 0.29),
                     QPointF(r.left() + w * 0.39, r.top() + h * 0.71),
                     QPointF(r.left() + w * 0.73, r.top() + h * 0.50)])
    p.setBrush(QColor("#ffffff"))
    p.setPen(QPen(QColor("#ffffff"), w * 0.05, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.drawPolygon(tri)
    p.restore()


def logo_pixmap(size: int) -> QPixmap:
    dpr = max(1.0, QGuiApplication.primaryScreen().devicePixelRatio()) if QGuiApplication.primaryScreen() else 1.0
    px = QPixmap(int(size * dpr), int(size * dpr))
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    paint_logo(p, QRectF(0, 0, size, size))
    p.end()
    return px


def app_icon() -> QIcon:
    ic = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        px = QPixmap(s, s)
        px.fill(Qt.GlobalColor.transparent)
        p = QPainter(px)
        paint_logo(p, QRectF(0, 0, s, s))
        p.end()
        ic.addPixmap(px)
    return ic
