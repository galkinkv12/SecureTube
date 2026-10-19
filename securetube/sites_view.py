from __future__ import annotations

import zlib
from typing import List, Optional, Set

from PySide6.QtCore import QPoint, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (QAbstractButton, QHBoxLayout, QLabel, QLineEdit, QMenu,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .dialogs import DarkDialog
from .extensions_view import FlowGrid
from .icons import icon
from .sitepolicy import Site, SiteError, new_site_id, parse_allow, parse_url
from .theme import C, R, flags, font
from .widgets import Segmented, Switch

AL = Qt.AlignmentFlag


def _chip(p: QPainter, x: float, y: float, text: str, color: str) -> float:
    p.setFont(font(11))
    w = QFontMetrics(p.font()).horizontalAdvance(text) + 14
    bg = QColor(color)
    bg.setAlpha(40)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(bg)
    p.drawRoundedRect(QRectF(x, y, w, 20), R["chip"], R["chip"])
    p.setPen(QColor(color))
    p.drawText(QRectF(x, y, w, 20), flags(AL.AlignCenter), text)
    return w + 6


class SiteCard(QAbstractButton):
    W, H = 252, 128
    editRequested = Signal(str)
    deleteRequested = Signal(str)

    def __init__(self, site: Site, catalog: bool = False, connected: bool = False):
        super().__init__()
        self.site, self.catalog, self.connected = site, catalog, connected
        self.setFixedSize(self.W, self.H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setToolTip(site.description or site.host)
        if not catalog:
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._menu)

    def _menu(self, pos: QPoint):
        m = QMenu(self)
        m.addAction(icon("play", C["text"], 18), "Открыть").triggered.connect(self.click)
        m.addAction(icon("edit", C["text"], 18), "Изменить…").triggered.connect(lambda: self.editRequested.emit(self.site.id))
        m.addSeparator()
        m.addAction(icon("trash", C["danger"], 18), "Удалить…").triggered.connect(lambda: self.deleteRequested.emit(self.site.id))
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
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(C["line2"] if self.underMouse() else C["line"]), 1))
        p.setBrush(QColor(C["panel"]))
        p.drawRoundedRect(r, R["frame"], R["frame"])
        # аватар: цвет зависит от названия, буква — первая
        hue = zlib.crc32(self.site.name.encode()) % 360
        av = QRectF(r.left() + 16, r.top() + 16, 48, 48)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor.fromHsl(hue, 150, 92))
        p.drawRoundedRect(av, R["btn"], R["btn"])
        p.setPen(QColor("#FFFFFF"))
        p.setFont(font(22, QFont.Weight.Bold))
        p.drawText(av, flags(AL.AlignCenter), (self.site.name[:1] or "?").upper())
        # название и адрес
        x = av.right() + 14
        w = r.right() - x - 14
        p.setPen(QColor(C["text"]))
        p.setFont(font(15, QFont.Weight.DemiBold))
        fm = QFontMetrics(p.font())
        p.drawText(QRectF(x, r.top() + 16, w, 22), flags(AL.AlignVCenter, AL.AlignLeft),
                   fm.elidedText(self.site.name, Qt.TextElideMode.ElideRight, int(w)))
        icon("lock", C["ok"], 14).paint(p, int(x), int(r.top() + 43), 14, 14)
        p.setPen(QColor(C["muted"]))
        p.setFont(font(12))
        fm = QFontMetrics(p.font())
        p.drawText(QRectF(x + 20, r.top() + 40, w - 20, 20), flags(AL.AlignVCenter, AL.AlignLeft),
                   fm.elidedText(self.site.host, Qt.TextElideMode.ElideRight, int(w - 20)))
        if self.catalog:
            p.setFont(font(12))
            desc = fm.elidedText(self.site.description, Qt.TextElideMode.ElideRight, int(r.width() - 32) * 2)
            p.setPen(QColor(C["muted"]))
            p.drawText(QRectF(r.left() + 16, r.top() + 72, r.width() - 32, 34), flags(AL.AlignTop, AL.AlignLeft, Qt.TextFlag.TextWordWrap), desc)
            label = "Подключено" if self.connected else "Подключить"
            p.setFont(font(12, QFont.Weight.DemiBold))
            tw = QFontMetrics(p.font()).horizontalAdvance(label) + 24
            pill = QRectF(r.right() - tw - 12, r.bottom() - 32, tw, 24)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C["line2"] if self.connected else C["accent"]))
            p.drawRoundedRect(pill, R["chip"] + 2, R["chip"] + 2)
            p.setPen(QColor(C["muted"] if self.connected else C["on_accent"]))
            p.drawText(pill, flags(AL.AlignCenter), label)
        else:
            cx, cy = r.left() + 16, r.top() + 78
            chips = []
            if not self.site.js:
                chips.append(("JavaScript выкл", C["muted"]))
            if self.site.persist:
                chips.append(("Вход сохраняется", C["danger"]))
            if self.site.allow:
                chips.append((f"+{len(self.site.allow)} доменов", C["accent2"]))
            if not chips:
                chips.append(("Изолирован", C["ok"]))
            for text, color in chips[:3]:
                cx += _chip(p, cx, cy, text, color)


class SiteDialog(DarkDialog):
    """Добавление и правка сайта. Всё вводимое проверяется sitepolicy."""

    def __init__(self, parent=None, site: Optional[Site] = None):
        super().__init__(parent)
        self.edit = site
        self.result_site: Optional[Site] = None
        self._ack = False
        self.setWindowTitle("Изменить сайт" if site else "Новый сайт")
        self.setFixedWidth(520)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(8)
        t = QLabel("Изменить сайт" if site else "Добавить сайт")
        t.setObjectName("h2")
        lay.addWidget(t)
        self.name = QLineEdit(site.name if site else "")
        self.name.setPlaceholderText("Название (необязательно)")
        self.name.setMaxLength(40)
        self.url = QLineEdit(site.url if site else "")
        self.url.setPlaceholderText("Адрес, например example.com")
        self.allow = QLineEdit(", ".join(site.allow) if site else "")
        self.allow.setPlaceholderText("Дополнительные домены через запятую (картинки, видео и т. п.)")
        for w in (self.name, self.url, self.allow):
            lay.addWidget(w)
        self.hint = QLabel("")
        self.hint.setObjectName("muted")
        self.hint.setWordWrap(True)
        self.hint.setMinimumHeight(38)
        lay.addWidget(self.hint)
        self.sw_js = self._switch(lay, "JavaScript", "Без него большинство современных сайтов не работает, зато безопаснее.", site.js if site else True)
        self.sw_fs = self._switch(lay, "Полный экран", "Разрешить сайту разворачивать видео на весь экран.", site.fullscreen if site else True)
        self.sw_persist = self._switch(lay, "Запоминать вход", "Cookie и данные сайта сохраняются на диске БЕЗ шифрования. "
                                       "Выключено: после закрытия всё забывается.", site.persist if site else False)
        self.msg = QLabel("")
        self.msg.setObjectName("error")
        self.msg.setWordWrap(True)
        self.msg.setMinimumHeight(36)
        lay.addWidget(self.msg)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("Сохранить" if site else "Добавить")
        self.ok.setObjectName("primary")
        self.ok.clicked.connect(self._submit)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)
        self.url.textChanged.connect(self._live)
        self.url.returnPressed.connect(self._submit)
        self._live()

    @staticmethod
    def _switch(lay: QVBoxLayout, title: str, desc: str, on: bool) -> Switch:
        row = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(QLabel(title))
        d = QLabel(desc)
        d.setObjectName("muted")
        d.setWordWrap(True)
        col.addWidget(d)
        s = Switch(on)
        row.addLayout(col, 1)
        row.addWidget(s, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addSpacing(4)
        lay.addLayout(row)
        return s

    def _live(self) -> None:
        self._ack = False
        text = self.url.text().strip()
        if not text:
            self.hint.setText("Откроется только этот сайт и его домены. Всё остальное будет заблокировано.")
            return
        try:
            p = parse_url(text)
            self.hint.setText(f"Откроется: {p.host}" + ("\n" + p.warnings[0] if p.warnings else ""))
        except SiteError as e:
            self.hint.setText(str(e))

    def _submit(self) -> None:
        try:
            p = parse_url(self.url.text())
            allow = parse_allow(self.allow.text())
        except SiteError as e:
            self.msg.setText(str(e))
            return
        if p.warnings and not self._ack:
            self._ack = True
            self.msg.setText(p.warnings[0] + "\nЕсли всё верно, нажмите кнопку ещё раз.")
            return
        name = " ".join(self.name.text().split())[:40] or p.host
        old = self.edit
        self.result_site = Site(id=old.id if old else new_site_id(), name=name, url=p.url, allow=allow,
                                js=self.sw_js.isChecked(), persist=self.sw_persist.isChecked(),
                                fullscreen=self.sw_fs.isChecked(), description=old.description if old else "",
                                source=old.source if old else "", added=old.added if old else 0.0)
        self.accept()


class SitesPage(QScrollArea):
    openSite = Signal(str)
    addRequested = Signal()
    editSite = Signal(str)
    deleteSite = Signal(str)
    connectRequested = Signal(str)

    def __init__(self):
        super().__init__()
        self._tab = "mine"
        self._mine: List[Site] = []
        self._catalog: List[Site] = []
        self._connected: Set[str] = set()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        col = QVBoxLayout(host)
        col.setContentsMargins(28, 20, 20, 32)
        col.setSpacing(14)
        self.setWidget(host)
        title = QLabel("Сайты")
        title.setObjectName("h1")
        sub = QLabel("Безопасный просмотр. Каждый сайт открывается в отдельной изолированной вкладке: разрешены только его "
                     "домены; трекеры, загрузки файлов, камера, геолокация, уведомления и всплывающие окна заблокированы всегда.")
        sub.setObjectName("muted")
        sub.setWordWrap(True)
        col.addWidget(title)
        col.addWidget(sub)
        self.warn = QLabel("Для просмотра сайтов нужен компонент QtWebEngine. Он входит в PySide6: выполните "
                           "«pip install -U PySide6» (или запустите install.bat) и перезапустите программу.")
        self.warn.setObjectName("error")
        self.warn.setWordWrap(True)
        self.warn.hide()
        col.addWidget(self.warn)
        row = QHBoxLayout()
        self.tabs = Segmented([("mine", "Мои сайты"), ("catalog", "Каталог")])
        self.tabs.setValue("mine")
        self.tabs.changed.connect(self._set_tab)
        self.b_add = QPushButton("＋  Добавить сайт")
        self.b_add.setObjectName("primary")
        self.b_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_add.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.b_add.clicked.connect(self.addRequested)
        row.addWidget(self.tabs)
        row.addStretch(1)
        row.addWidget(self.b_add)
        col.addLayout(row)
        self.empty = QLabel("")
        self.empty.setObjectName("muted")
        self.empty.setWordWrap(True)
        self.empty.hide()
        col.addWidget(self.empty)
        self.grid = FlowGrid(SiteCard.W, SiteCard.H, 12)
        col.addWidget(self.grid)
        col.addStretch(1)

    def _set_tab(self, key: str) -> None:
        self._tab = key
        self._fill()

    def refresh(self, mine: List[Site], catalog: List[Site], connected: Set[str], has_web: bool) -> None:
        self._mine, self._catalog, self._connected = mine, catalog, connected
        self.warn.setVisible(not has_web)
        self._fill()

    def _fill(self) -> None:
        cards = []
        if self._tab == "mine":
            for s in sorted(self._mine, key=lambda x: x.name.casefold()):
                c = SiteCard(s)
                c.clicked.connect(lambda _=False, i=s.id: self.openSite.emit(i))
                c.editRequested.connect(self.editSite)
                c.deleteRequested.connect(self.deleteSite)
                cards.append(c)
            self.empty.setVisible(not cards)
            self.empty.setText("Пока нет сайтов. Нажмите «Добавить сайт» или подключите готовый из каталога.")
        else:
            for s in self._catalog:
                c = SiteCard(s, catalog=True, connected=s.id in self._connected)
                c.clicked.connect(lambda _=False, i=s.id: self.connectRequested.emit(i))
                cards.append(c)
            self.empty.setVisible(not cards)
            self.empty.setText("Каталог пуст. Описания сайтов-коннекторов можно установить в разделе «Расширения».")
        self.grid.set_items(cards)
