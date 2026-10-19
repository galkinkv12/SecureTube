from __future__ import annotations

from typing import List, Tuple

from PySide6.QtCore import QEasingCurve, QPoint, Qt, QVariantAnimation, Signal
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .widgets import NavItem, icon_button

EXPANDED, COMPACT = 244, 72


class Sidebar(QWidget):
    navigate = Signal(str)
    addCategory = Signal()
    categoryMenu = Signal(str, QPoint)

    def __init__(self):
        super().__init__()
        self.compact = False
        self.setFixedWidth(EXPANDED)
        self._cat_items: List[NavItem] = []
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 6, 0, 12)
        lay.setSpacing(2)
        self.n_all = self._nav("all", "grid", "Все видео", 0)
        self.n_fav = self._nav("fav", "star", "Избранное", 0)
        lay.addWidget(self.n_all)
        lay.addWidget(self.n_fav)

        self.cat_head = QWidget()
        h = QHBoxLayout(self.cat_head)
        h.setContentsMargins(24, 14, 12, 0)
        t = QLabel("Категории")
        t.setObjectName("muted")
        self.b_add = icon_button("plus", "Новая категория", 30, 16)
        self.b_add.clicked.connect(self.addCategory)
        h.addWidget(t, 1)
        h.addWidget(self.b_add)
        lay.addWidget(self.cat_head)
        self.cat_box = QVBoxLayout()
        self.cat_box.setSpacing(2)
        lay.addLayout(self.cat_box)
        lay.addStretch(1)
        self.n_sites = self._nav("sites", "globe", "Сайты", None)
        self.n_ext = self._nav("ext", "palette", "Расширения", None)
        self.n_set = self._nav("settings", "gear", "Настройки", None)
        lay.addWidget(self.n_sites)
        lay.addWidget(self.n_ext)
        lay.addWidget(self.n_set)
        self.n_all.setChecked(True)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(210)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(lambda v: self.setFixedWidth(int(v)))

    def _nav(self, key, ic, text, count) -> NavItem:
        it = NavItem(key, ic, text, count)
        self.group.addButton(it)
        it.clicked.connect(lambda _=False, k=key: self.navigate.emit(k))
        return it

    def _all_items(self):
        return [self.n_all, self.n_fav, self.n_sites, self.n_ext, self.n_set] + self._cat_items

    def set_counts(self, total: int, fav: int) -> None:
        self.n_all.set_count(total)
        self.n_fav.set_count(fav)

    def set_categories(self, cats: List[Tuple[str, int]], current: str) -> None:
        for it in self._cat_items:
            self.group.removeButton(it)
            self.cat_box.removeWidget(it)
            it.deleteLater()
        self._cat_items = []
        for name, count in cats:
            it = self._nav("cat:" + name, "tag", name, count)
            it.set_compact(self.compact)
            it.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            it.customContextMenuRequested.connect(lambda pos, n=name, w=it: self.categoryMenu.emit(n, w.mapToGlobal(pos)))
            self.cat_box.addWidget(it)
            self._cat_items.append(it)
        self.select(current)

    def select(self, key: str) -> None:
        for it in self._all_items():
            if it.key == key:
                it.setChecked(True)
                return
        self.n_all.setChecked(True)

    def uncheck_all(self) -> None:
        self.group.setExclusive(False)
        for it in self._all_items():
            it.setChecked(False)
        self.group.setExclusive(True)

    def set_compact(self, on: bool, animate: bool = True) -> None:
        self.compact = on
        for it in self._all_items():
            it.set_compact(on)
        self.cat_head.setVisible(not on)
        target = COMPACT if on else EXPANDED
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self.width())
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self.setFixedWidth(target)
