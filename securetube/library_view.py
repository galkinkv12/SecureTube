from __future__ import annotations

import zlib

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListView, QMenu, QPushButton, QStackedWidget,
                               QStyle, QStyledItemDelegate, QVBoxLayout, QWidget)

from . import theme
from .icons import icon, logo_pixmap
from .models import CurrentRole, ItemRole, MissingRole, ThumbRole
from .theme import C, R, flags, font
from .util import fmt_added, fmt_ms

PAD = 8
MIN_CARD = {0: 220, 1: 280, 2: 360}
SORT_LABELS = [("added_desc", "Сначала новые"), ("added_asc", "Сначала старые"),
               ("title_asc", "По названию А–Я"), ("title_desc", "По названию Я–А"),
               ("dur_desc", "Самые длинные"), ("dur_asc", "Самые короткие"),
               ("size_desc", "Самые большие")]
AL = Qt.AlignmentFlag


def card_height(cell_w: int) -> int:
    return int((cell_w - 2 * PAD) * 9 / 16) + 2 * PAD + 10 + 22 + 22


def draw_placeholder(p: QPainter, r: QRectF, key: str) -> None:
    h = zlib.crc32(key.encode()) % 360
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0, QColor.fromHsl(h, 150, 92))
    g.setColorAt(1, QColor.fromHsl((h + 50) % 360, 150, 48))
    p.fillRect(r, QBrush(g))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 40))
    c = r.center()
    s = min(r.width(), r.height()) * 0.16
    path = QPainterPath()
    path.moveTo(c.x() - s * 0.6, c.y() - s)
    path.lineTo(c.x() - s * 0.6, c.y() + s)
    path.lineTo(c.x() + s, c.y())
    path.closeSubpath()
    p.drawPath(path)


class CardDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cw, self.ch = 280, card_height(280)
        self.hover_row, self.hover_t = -1, 0.0

    def sizeHint(self, option, index):
        return QSize(self.cw, self.ch)

    def paint(self, p, opt, idx):
        item = idx.data(ItemRole)
        if not item:
            return
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        t = self.hover_t if idx.row() == self.hover_row else 0.0
        card = QRectF(opt.rect).adjusted(PAD, PAD, -PAD, -PAD)
        th = QRectF(card.left(), card.top(), card.width(), card.width() * 9 / 16)

        clip = QPainterPath()
        clip.addRoundedRect(th, R["card"], R["card"])
        p.setClipPath(clip)
        pm = idx.data(ThumbRole)
        if pm is not None and not pm.isNull():
            k = 1.0 + 0.05 * t
            w, h = th.width() * k, th.height() * k
            p.drawPixmap(QRectF(th.center().x() - w / 2, th.center().y() - h / 2, w, h), pm, QRectF(pm.rect()))
        else:
            draw_placeholder(p, th, item["id"])
        missing = bool(idx.data(MissingRole))
        if missing:
            p.fillRect(th, QColor(12, 13, 17, 215))
            p.setPen(QColor(C["muted"]))
            p.setFont(font(13))
            p.drawText(th, flags(AL.AlignCenter), "Файл не найден")
        elif t > 0:
            p.fillRect(th, QColor(0, 0, 0, int(95 * t)))
            p.setOpacity(t)
            c = th.center()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C["accent"]))
            p.drawEllipse(c, 24, 24)
            p.setBrush(QColor(C["on_accent"]))
            tri = QPainterPath()
            tri.moveTo(c.x() - 6, c.y() - 10)
            tri.lineTo(c.x() - 6, c.y() + 10)
            tri.lineTo(c.x() + 11, c.y())
            tri.closeSubpath()
            p.drawPath(tri)
            p.setOpacity(1.0)
        p.setClipping(False)

        if item["dur"] > 0:
            txt = fmt_ms(item["dur"])
            p.setFont(font(12, QFont.Weight.DemiBold))
            tw = QFontMetrics(p.font()).horizontalAdvance(txt)
            b = QRectF(th.right() - tw - 20, th.bottom() - 28, tw + 12, 20)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 175))
            p.drawRoundedRect(b, 6, 6)
            p.setPen(QColor("#ffffff"))
            p.drawText(b, flags(AL.AlignCenter), txt)
        if item["fav"]:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 150))
            p.drawEllipse(QRectF(th.right() - 36, th.top() + 8, 28, 28))
            icon("star_f", C["accent"], 16).paint(p, int(th.right() - 30), int(th.top() + 14), 16, 16)

        if t > 0:
            p.setPen(QPen(QColor(255, 255, 255, int(40 * t)), 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(th.adjusted(.5, .5, -.5, -.5), R["card"], R["card"])

        y = th.bottom() + 10
        p.setFont(font(14, QFont.Weight.DemiBold))
        p.setPen(QColor(C["text"]))
        fm = QFontMetrics(p.font())
        p.drawText(QRectF(card.left() + 2, y, card.width() - 4, 22), flags(AL.AlignVCenter, AL.AlignLeft),
                   fm.elidedText(item["title"], Qt.TextElideMode.ElideRight, int(card.width() - 4)))
        y += 22
        p.setFont(font(12))
        fm = QFontMetrics(p.font())
        right_w = 0
        if item["cat"]:
            cat = fm.elidedText(item["cat"], Qt.TextElideMode.ElideRight, int(card.width() * 0.45))
            cwid = fm.horizontalAdvance(cat) + 16
            chip = QRectF(card.right() - cwid - 2, y + 1, cwid, 19)
            p.setPen(Qt.PenStyle.NoPen)
            chip_bg = QColor(C["accent2"])
            chip_bg.setAlpha(46)
            p.setBrush(chip_bg)
            p.drawRoundedRect(chip, R["chip"], R["chip"])
            chip_fg = QColor(C["accent2"])
            p.setPen(chip_fg.lighter(140) if theme.IS_DARK else chip_fg.darker(115))
            p.drawText(chip, flags(AL.AlignCenter), cat)
            right_w = cwid + 8
        p.setPen(QColor(C["muted"]))
        p.drawText(QRectF(card.left() + 2, y, card.width() - 4 - right_w, 21), flags(AL.AlignVCenter, AL.AlignLeft),
                   fm.elidedText(fmt_added(item["added"]), Qt.TextElideMode.ElideRight, int(card.width() - 4 - right_w)))
        p.restore()


class CompactDelegate(QStyledItemDelegate):
    H = 76

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.H)

    def paint(self, p, opt, idx):
        item = idx.data(ItemRole)
        if not item:
            return
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(opt.rect).adjusted(4, 3, -4, -3)
        cur = bool(idx.data(CurrentRole))
        hov = bool(opt.state & QStyle.StateFlag.State_MouseOver)
        if cur or hov:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(C["raised"] if cur else C["hover"]))
            p.drawRoundedRect(r, R["btn"] + 2, R["btn"] + 2)
        th = QRectF(r.left() + 6, r.top() + 6, 96, 54)
        clip = QPainterPath()
        clip.addRoundedRect(th, R["seg"], R["seg"])
        p.setClipPath(clip)
        pm = idx.data(ThumbRole)
        if pm is not None and not pm.isNull():
            p.drawPixmap(th, pm, QRectF(pm.rect()))
        else:
            draw_placeholder(p, th, item["id"])
        p.setClipping(False)
        if item["dur"] > 0:
            txt = fmt_ms(item["dur"])
            p.setFont(font(11, QFont.Weight.DemiBold))
            tw = QFontMetrics(p.font()).horizontalAdvance(txt)
            b = QRectF(th.right() - tw - 12, th.bottom() - 18, tw + 8, 15)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 175))
            p.drawRoundedRect(b, 4, 4)
            p.setPen(QColor("#ffffff"))
            p.drawText(b, flags(AL.AlignCenter), txt)
        x = th.right() + 12
        p.setFont(font(13, QFont.Weight.DemiBold if cur else QFont.Weight.Normal))
        p.setPen(QColor(C["accent"] if cur else C["text"]))
        fm = QFontMetrics(p.font())
        avail = int(r.right() - x - 8)
        title = item["title"]
        first = ""
        for w in title.split(" "):
            trial = (first + " " + w).strip()
            if fm.horizontalAdvance(trial) <= avail:
                first = trial
            else:
                break
        if not first:
            lines = [fm.elidedText(title, Qt.TextElideMode.ElideRight, avail)]
        else:
            rest = title[len(first):].strip()
            lines = [first] + ([fm.elidedText(rest, Qt.TextElideMode.ElideRight, avail)] if rest else [])
        for i, ln in enumerate(lines):
            p.drawText(QRectF(x, th.top() + 2 + i * 18, r.right() - x - 8, 18), flags(AL.AlignVCenter, AL.AlignLeft), ln)
        p.restore()


class GridView(QListView):
    clickedId = Signal(str)
    contextId = Signal(str, QPoint)

    def __init__(self):
        super().__init__()
        self.delegate = CardDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setUniformItemSizes(True)
        self.setSpacing(0)
        self.setMouseTracking(True)
        self.setSelectionMode(QListView.SelectionMode.NoSelection)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.verticalScrollBar().setSingleStep(40)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._ctx)
        self.clicked.connect(lambda i: self.clickedId.emit(self._id(i)))
        self.card_size = 1
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(170)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.valueChanged.connect(self._tick)

    def _id(self, idx) -> str:
        item = idx.data(ItemRole)
        return item["id"] if item else ""

    def _ctx(self, pos):
        idx = self.indexAt(pos)
        if idx.isValid():
            self.contextId.emit(self._id(idx), self.viewport().mapToGlobal(pos))

    def _tick(self, v):
        self.delegate.hover_t = float(v)
        self.viewport().update()

    def mouseMoveEvent(self, e):
        idx = self.indexAt(e.position().toPoint())
        row = idx.row() if idx.isValid() else -1
        if row != self.delegate.hover_row:
            self.delegate.hover_row = row
            self.delegate.hover_t = 0.0
            self._anim.stop()
            if row >= 0:
                self._anim.start()
            self.viewport().update()
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if row >= 0 else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self.delegate.hover_row = -1
        self._anim.stop()
        self.viewport().update()
        super().leaveEvent(e)

    def set_card_size(self, size: int) -> None:
        self.card_size = size
        self.relayout()

    def relayout(self) -> None:
        w = self.viewport().width()
        if w <= 0:
            return
        cols = max(1, w // MIN_CARD.get(self.card_size, 280))
        cw = w // cols
        self.delegate.cw, self.delegate.ch = cw, card_height(cw)
        self.setGridSize(QSize(cw, self.delegate.ch))
        self.doItemsLayout()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.relayout()


class EmptyState(QWidget):
    addRequested = Signal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(8)
        self.mark = QLabel()
        self.mark.setPixmap(logo_pixmap(72))
        self.mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel()
        self.title.setObjectName("h1")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text = QLabel()
        self.text.setObjectName("muted")
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.setWordWrap(True)
        self.btn = QPushButton("＋  Добавить видео")
        self.btn.setObjectName("primary")
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.clicked.connect(self.addRequested)
        self.hint = QLabel("Файлы и папки можно просто перетащить в окно")
        self.hint.setObjectName("muted")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for w in (self.mark, self.title, self.text):
            lay.addWidget(w)
        lay.addSpacing(10)
        lay.addWidget(self.btn, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addSpacing(4)
        lay.addWidget(self.hint)

    def show_kind(self, kind: str, scope: str = "all") -> None:
        if kind == "empty":
            self.title.setText("Здесь пока пусто")
            self.text.setText("Добавьте видео — они останутся только на этом компьютере.")
            self.btn.show(); self.hint.show(); self.mark.show()
        else:
            self.title.setText("Ничего не найдено")
            msgs = {"fav": "Отметьте видео звёздочкой в меню карточки — они появятся здесь.",
                    "cat": "В этой категории пока нет видео. Назначьте её через меню карточки."}
            self.text.setText(msgs.get(scope.split(":")[0], "Попробуйте изменить запрос."))
            self.btn.hide(); self.hint.hide(); self.mark.hide()


class LibraryPage(QWidget):
    addRequested = Signal()
    sortChanged = Signal(str)

    def __init__(self, proxy):
        super().__init__()
        self.proxy = proxy
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 12, 0)
        lay.setSpacing(6)
        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = QLabel("Все видео")
        self.title.setObjectName("h1")
        self.summary = QLabel("")
        self.summary.setObjectName("muted")
        col.addWidget(self.title)
        col.addWidget(self.summary)
        head.addLayout(col, 1)
        self.sort_btn = QPushButton()
        self.sort_btn.setObjectName("ghost")
        self.sort_btn.setIcon(icon("sort", C["muted"], 18))
        self.sort_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sort_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sort_btn.clicked.connect(self._sort_menu)
        head.addWidget(self.sort_btn, 0, Qt.AlignmentFlag.AlignBottom)
        lay.addLayout(head)
        self.stack = QStackedWidget()
        self.view = GridView()
        self.view.setModel(proxy)
        self.empty = EmptyState()
        self.empty.addRequested.connect(self.addRequested)
        self.stack.addWidget(self.view)
        self.stack.addWidget(self.empty)
        lay.addWidget(self.stack, 1)
        self.set_sort("added_desc")

    def retheme(self) -> None:
        self.sort_btn.setIcon(icon("sort", C["muted"], 18))
        self.empty.mark.setPixmap(logo_pixmap(72))

    def set_sort(self, mode: str) -> None:
        self.mode = mode
        label = dict(SORT_LABELS).get(mode, "")
        self.sort_btn.setText("  " + label)

    def _sort_menu(self):
        m = QMenu(self)
        for key, label in SORT_LABELS:
            a = m.addAction(label)
            a.setCheckable(True)
            a.setChecked(key == self.mode)
            a.triggered.connect(lambda _=False, k=key: (self.set_sort(k), self.sortChanged.emit(k)))
        m.exec(self.sort_btn.mapToGlobal(QPoint(0, self.sort_btn.height() + 4)))

    def refresh(self, title: str, scope: str, total_items: int, summary: str, shown: int) -> None:
        self.title.setText(title)
        self.summary.setText(summary)
        if shown == 0:
            self.empty.show_kind("empty" if total_items == 0 else "none", scope)
            self.stack.setCurrentWidget(self.empty)
        else:
            self.stack.setCurrentWidget(self.view)
