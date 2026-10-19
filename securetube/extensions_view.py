from __future__ import annotations

import random
from typing import List, Optional

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen, QBrush
from PySide6.QtWidgets import (QAbstractButton, QFrame, QHBoxLayout, QLabel, QMenu, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from .extensions import ExtensionManager, Theme
from .icons import icon
from .theme import C, flags, font
from .widgets import Segmented, hline

AL = Qt.AlignmentFlag
EXAMPLE = ('{\n  "type": "theme",\n  "id": "my-theme",\n  "name": "Моя тема",\n  "radius": 14,\n'
           '  "colors": {\n    "bg": "#0B0F1A",\n    "text": "#E6EAF5",\n    "accent": "#5B8CFF",\n    "accent2": "#A78BFA"\n  }\n}')


class FlowGrid(QWidget):

    def __init__(self, cell_w: int, cell_h: int, gap: int = 10):
        super().__init__()
        self.cw, self.ch, self.gap = cell_w, cell_h, gap
        self._items: List[QWidget] = []

    def set_items(self, widgets: List[QWidget]) -> None:
        for w in self._items:
            w.setParent(None)
            w.deleteLater()
        self._items = list(widgets)
        for w in self._items:
            w.setParent(self)
            w.show()
        self._layout()

    def _layout(self) -> None:
        w = max(self.width(), self.cw)
        cols = max(1, (w + self.gap) // (self.cw + self.gap))
        for i, wd in enumerate(self._items):
            r, c = divmod(i, cols)
            wd.setGeometry(c * (self.cw + self.gap), r * (self.ch + self.gap), self.cw, self.ch)
        rows = (len(self._items) + cols - 1) // cols
        self.setMinimumHeight(max(0, rows * (self.ch + self.gap) - self.gap))

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._layout()


class ThemeCard(QAbstractButton):
    W, H = 212, 158
    removeRequested = Signal(str)

    def __init__(self, t: Theme, active: bool):
        super().__init__()
        self.t, self.active = t, active
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(t.name + (f"\nАвтор: {t.author}" if t.author else ""))
        if t.source == "user":
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._menu)

    def _menu(self, pos: QPoint):
        m = QMenu(self)
        m.addAction(icon("trash", C["danger"], 18), "Удалить тему").triggered.connect(lambda: self.removeRequested.emit(self.t.id))
        m.exec(self.mapToGlobal(pos))

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self.t.colors
        r = QRectF(self.rect()).adjusted(3, 3, -3, -3)
        prev = QRectF(r.left(), r.top(), r.width(), 110)
        rad = min(self.t.radius, 14) * 0.85 + 2
        clip = QPainterPath()
        clip.addRoundedRect(prev, rad, rad)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(c["bg"]))
        p.drawPath(clip)
        p.setClipPath(clip)
        p.setBrush(QColor(c["panel"]))
        p.drawRect(QRectF(prev.left(), prev.top(), 28, prev.height()))
        for i in range(4):
            p.setBrush(QColor(c["accent"] if i == 0 else c["line2"]))
            p.drawRoundedRect(QRectF(prev.left() + 8, prev.top() + 16 + i * 15, 12, 6), 3, 3)
        p.setBrush(QColor(c["raised"]))
        p.drawRoundedRect(QRectF(prev.left() + 38, prev.top() + 8, prev.width() - 104, 11), 5.5, 5.5)
        p.setBrush(QColor(c["accent"]))
        p.drawRoundedRect(QRectF(prev.right() - 58, prev.top() + 7, 50, 13), 6.5, 6.5)
        x0, avail, gap = prev.left() + 38, prev.width() - 48, 6
        cw = (avail - 2 * gap) / 3
        th = cw * 9 / 16
        for row in range(2):
            y = prev.top() + 30 + row * (th + 19)
            for i in range(3):
                x = x0 + i * (cw + gap)
                tr = QRectF(x, y, cw, th)
                if row == 0 and i == 0:
                    g = QLinearGradient(tr.topLeft(), tr.bottomRight())
                    g.setColorAt(0, QColor(c["accent"]))
                    g.setColorAt(1, QColor(c["accent2"]))
                    p.setBrush(QBrush(g))
                else:
                    p.setBrush(QColor(c["hover"] if (i + row) % 2 else c["raised"]))
                p.drawRoundedRect(tr, min(5, rad), min(5, rad))
                p.setBrush(QColor(c["text"]))
                p.drawRoundedRect(QRectF(x, y + th + 4, cw * 0.82, 3.5), 1.7, 1.7)
                p.setBrush(QColor(c["muted"]))
                p.drawRoundedRect(QRectF(x, y + th + 10, cw * 0.5, 3), 1.5, 1.5)
        p.setClipping(False)
        if self.active:
            p.setPen(QPen(QColor(C["accent"]), 2))
        else:
            p.setPen(QPen(QColor(C["line2"] if not self.underMouse() else C["muted"]), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(prev.adjusted(.5, .5, -.5, -.5), rad, rad)
        if self.active:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C["accent"]))
            p.drawEllipse(QRectF(prev.right() - 28, prev.top() + 36, 20, 20))
            icon("check", C["on_accent"], 14).paint(p, int(prev.right() - 25), int(prev.top() + 39), 14, 14)
        p.setPen(QColor(C["text"]))
        p.setFont(font(13, QFont.Weight.DemiBold))
        fm = QFontMetrics(p.font())
        p.drawText(QRectF(r.left() + 2, prev.bottom() + 8, r.width() - 4, 20), flags(AL.AlignVCenter, AL.AlignLeft),
                   fm.elidedText(self.t.name, Qt.TextElideMode.ElideRight, int(r.width() - 4)))
        p.setPen(QColor(C["muted"]))
        p.setFont(font(12))
        sub = ("Тёмная" if self.t.dark else "Светлая") + (", своя" if self.t.source == "user" else "")
        p.drawText(QRectF(r.left() + 2, prev.bottom() + 27, r.width() - 4, 18), flags(AL.AlignVCenter, AL.AlignLeft), sub)


class AccentSwatch(QAbstractButton):
    W, H = 100, 92

    def __init__(self, name: str, c1: str, c2: Optional[str], active: bool, tip: str = ""):
        super().__init__()
        self.name, self.c1, self.c2, self.active = name, c1, c2, active
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(tip or name)

    def enterEvent(self, e):
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self.update()
        super().leaveEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy, d = self.width() / 2, 34.0, 46.0
        circle = QRectF(cx - d / 2, cy - d / 2, d, d)
        if self.active or self.underMouse():
            p.setPen(QPen(QColor(C["text"] if self.active else C["line2"]), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(circle.adjusted(-5, -5, 5, 5))
        p.setPen(Qt.PenStyle.NoPen)
        if self.c2:
            g = QLinearGradient(circle.topLeft(), circle.bottomRight())
            g.setColorAt(0, QColor(self.c1))
            g.setColorAt(1, QColor(self.c2))
            p.setBrush(QBrush(g))
        else:
            p.setBrush(QColor(self.c1))
        p.drawEllipse(circle)
        if self.active:
            ic = icon("check", "#000000" if QColor(self.c1).lightness() > 150 else "#FFFFFF", 20)
            ic.paint(p, int(cx - 10), int(cy - 10), 20, 20)
        p.setPen(QColor(C["text"] if self.active else C["muted"]))
        p.setFont(font(12))
        fm = QFontMetrics(p.font())
        p.drawText(QRectF(2, 64, self.width() - 4, 20), flags(AL.AlignCenter),
                   fm.elidedText(self.name, Qt.TextElideMode.ElideRight, self.width() - 6))


class ExtensionsPage(QScrollArea):
    themeChosen = Signal(str)
    accentChosen = Signal(str)          
    installRequested = Signal()
    openFolder = Signal()
    rescan = Signal()
    removeRequested = Signal(str, str)  

    def __init__(self):
        super().__init__()
        self._ext: Optional[ExtensionManager] = None
        self._theme_id, self._accent_id = "securetube", ""
        self._filter = "all"
        self._shown: List[Theme] = []
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        col = QVBoxLayout(host)
        col.setContentsMargins(28, 20, 20, 32)
        col.setSpacing(14)
        self.setWidget(host)

        title = QLabel("Расширения")
        title.setObjectName("h1")
        sub = QLabel("Темы и акценты оформления. Расширения — обычные JSON-файлы без кода: они только меняют цвета "
                     "и скругления и не могут получить доступ к вашим видео.")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        col.addWidget(title)
        col.addWidget(sub)
        self.tabs = Segmented([("themes", "Темы"), ("accents", "Акценты"), ("manage", "Управление")])
        self.tabs.setValue("themes")
        self.tabs.changed.connect(self._tab)
        tab_row = QHBoxLayout()
        tab_row.addWidget(self.tabs)
        tab_row.addStretch(1)
        col.addLayout(tab_row)
        # --- темы
        tp = QWidget()
        tl = QVBoxLayout(tp)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(12)
        top = QHBoxLayout()
        self.filter = Segmented([("all", "Все"), ("dark", "Тёмные"), ("light", "Светлые")])
        self.filter.setValue("all")
        self.filter.changed.connect(self._set_filter)
        self.count = QLabel("")
        self.count.setObjectName("muted")
        self.b_random = QPushButton("Случайная тема")
        self.b_random.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_random.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.b_random.clicked.connect(self._random)
        top.addWidget(self.filter)
        top.addSpacing(12)
        top.addWidget(self.count)
        top.addStretch(1)
        top.addWidget(self.b_random)
        tl.addLayout(top)
        self.theme_grid = FlowGrid(ThemeCard.W, ThemeCard.H, 12)
        tl.addWidget(self.theme_grid)
        tl.addStretch(1)
        col.addWidget(tp)

        # --- акценты
        ap = QWidget()
        al = QVBoxLayout(ap)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(12)
        hint = QLabel("Акцент перекрашивает кнопки, ползунок, значки и подсветку поверх любой темы.")
        hint.setObjectName("muted")
        al.addWidget(hint)
        self.accent_grid = FlowGrid(AccentSwatch.W, AccentSwatch.H, 8)
        al.addWidget(self.accent_grid)
        al.addStretch(1)
        col.addWidget(ap)
        ap.hide()

        # --- управление
        mp = QWidget()
        ml = QVBoxLayout(mp)
        ml.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(22, 18, 22, 18)
        cl.setSpacing(12)
        self._row(cl, "Установить из файла", "Один файл темы, набор акцентов или целый пакет (.json).", "Выбрать файлы…", self.installRequested)
        cl.addWidget(hline())
        self._row(cl, "Папка расширений", "Сюда можно просто положить файлы .json, затем нажать «Обновить».", "Открыть папку", self.openFolder)
        cl.addWidget(hline())
        self._row(cl, "Обновить список", "Перечитывает встроенные и свои расширения.", "Обновить", self.rescan)
        ml.addWidget(card)
        self.stats = QLabel("")
        self.stats.setObjectName("muted")
        self.stats.setWordWrap(True)
        self.errors = QLabel("")
        self.errors.setObjectName("error")
        self.errors.setWordWrap(True)
        self.errors.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        howto = QLabel("Как сделать свою тему: создайте файл .json (достаточно четырёх цветов, остальные вычисляются) и установите его.")
        howto.setObjectName("muted")
        howto.setWordWrap(True)
        self.example = QLabel(EXAMPLE)
        self.example.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.example.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 13px;")
        ml.addWidget(self.stats)
        ml.addWidget(self.errors)
        ml.addSpacing(6)
        ml.addWidget(howto)
        ml.addWidget(self.example)
        ml.addStretch(1)
        col.addWidget(mp)
        mp.hide()
        self._pages = [tp, ap, mp]
        col.addStretch(1)

    @staticmethod
    def _row(lay: QVBoxLayout, title: str, desc: str, button: str, signal) -> None:
        row = QHBoxLayout()
        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(QLabel(title))
        d = QLabel(desc)
        d.setObjectName("muted")
        d.setWordWrap(True)
        left.addWidget(d)
        b = QPushButton(button)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        b.clicked.connect(signal)
        row.addLayout(left, 1)
        row.addWidget(b, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addLayout(row)

    # --- состояние
    def _tab(self, key: str) -> None:
        idx = {"themes": 0, "accents": 1, "manage": 2}[key]
        for i, pg in enumerate(self._pages):
            pg.setVisible(i == idx)

    def _set_filter(self, key: str) -> None:
        self._filter = key
        self._fill_themes()

    def refresh(self, ext: ExtensionManager, theme_id: str, accent_id: str) -> None:
        self._ext, self._theme_id, self._accent_id = ext, theme_id, accent_id
        self._fill_themes()
        self._fill_accents()
        user_t = sum(1 for t in ext.themes.values() if t.source == "user")
        user_a = sum(1 for a in ext.accents.values() if a.source == "user")
        self.stats.setText(f"Тем: {len(ext.themes)} (своих: {user_t}). Акцентов: {len(ext.accents)} (своих: {user_a}).")
        self.errors.setVisible(bool(ext.errors))
        self.errors.setText("Не удалось прочитать:\n" + "\n".join(ext.errors[:8]) if ext.errors else "")

    def _fill_themes(self) -> None:
        if not self._ext:
            return
        themes = [t for t in self._ext.ordered_themes()
                  if self._filter == "all" or ("dark" if t.dark else "light") == self._filter]
        self._shown = themes
        cards = []
        for t in themes:
            c = ThemeCard(t, t.id == self._theme_id)
            c.clicked.connect(lambda _=False, i=t.id: self.themeChosen.emit(i))
            c.removeRequested.connect(lambda i: self.removeRequested.emit("theme", i))
            cards.append(c)
        self.theme_grid.set_items(cards)
        self.count.setText(f"{len(themes)} шт.")

    def _fill_accents(self) -> None:
        if not self._ext:
            return
        cur = self._ext.theme(self._theme_id).colors
        items = [AccentSwatch("Из темы", cur["accent"], cur["accent2"], not self._accent_id, "Цвета самой темы")]
        items[0].clicked.connect(lambda _=False: self.accentChosen.emit(""))
        for a in self._ext.accents.values():
            s = AccentSwatch(a.name, a.accent, a.accent2, a.id == self._accent_id)
            s.clicked.connect(lambda _=False, i=a.id: self.accentChosen.emit(i))
            items.append(s)
        self.accent_grid.set_items(items)

    def _random(self) -> None:
        pool = [t for t in self._shown if t.id != self._theme_id]
        if pool:
            self.themeChosen.emit(random.choice(pool).id)
