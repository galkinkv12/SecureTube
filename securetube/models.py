from __future__ import annotations

from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QAbstractListModel, QModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtGui import QPixmap

from .util import natural_key

ItemRole = int(Qt.ItemDataRole.UserRole) + 1
ThumbRole = int(Qt.ItemDataRole.UserRole) + 2
MissingRole = int(Qt.ItemDataRole.UserRole) + 3
CurrentRole = int(Qt.ItemDataRole.UserRole) + 4
_PIX_LIMIT = 400


class LibraryModel(QAbstractListModel):
    def __init__(self, core, parent=None):
        super().__init__(parent)
        self.core = core
        self._ids: List[str] = list(core.library.items)
        self._row: Dict[str, int] = {i: n for n, i in enumerate(self._ids)}
        self._pix: "OrderedDict[str, Optional[QPixmap]]" = OrderedDict()
        self.missing: set = set()

    # --- Qt
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._ids)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._ids):
            return None
        it = self.core.library.items.get(self._ids[index.row()])
        if it is None:
            return None
        if role == ItemRole:
            return it
        if role == ThumbRole:
            return self.pixmap(it["id"]) if it["th"] else None
        if role == MissingRole:
            return it["id"] in self.missing
        if role == int(Qt.ItemDataRole.DisplayRole):
            return it["title"]
        return None

    # --- доступ без конвертации в QVariant
    def item_at(self, row: int) -> dict:
        return self.core.library.items[self._ids[row]]

    def item(self, item_id: str) -> Optional[dict]:
        return self.core.library.items.get(item_id)

    def row_of(self, item_id: str) -> int:
        return self._row.get(item_id, -1)

    # --- изменения
    def add_item(self, item: dict) -> None:
        n = len(self._ids)
        self.beginInsertRows(QModelIndex(), n, n)
        self.core.library.add(item)
        self._ids.append(item["id"])
        self._row[item["id"]] = n
        self.endInsertRows()

    def remove_item(self, item_id: str) -> None:
        r = self._row.get(item_id)
        if r is None:
            return
        self.beginRemoveRows(QModelIndex(), r, r)
        self._ids.pop(r)
        self.core.library.remove(item_id)
        self._pix.pop(item_id, None)
        self._row = {i: n for n, i in enumerate(self._ids)}
        self.endRemoveRows()

    def reset_all(self) -> None:
        self.beginResetModel()
        self._ids = list(self.core.library.items)
        self._row = {i: n for n, i in enumerate(self._ids)}
        self._pix.clear()
        self.endResetModel()

    def changed(self, item_id: str) -> None:
        r = self._row.get(item_id, -1)
        if r >= 0:
            i = self.index(r)
            self.dataChanged.emit(i, i)

    def set_missing(self, ids: set) -> None:
        if ids != self.missing:
            self.missing = set(ids)
            if self._ids:
                self.dataChanged.emit(self.index(0), self.index(len(self._ids) - 1))

    # --- превью
    def pixmap(self, item_id: str) -> Optional[QPixmap]:
        if item_id in self._pix:
            self._pix.move_to_end(item_id)
            return self._pix[item_id]
        pm: Optional[QPixmap] = None
        data = self.core.thumbs.load(item_id)
        if data:
            tmp = QPixmap()
            if tmp.loadFromData(data, "JPG"):
                pm = tmp
        self._pix[item_id] = pm
        while len(self._pix) > _PIX_LIMIT:
            self._pix.popitem(last=False)
        return pm

    def drop_pixmap(self, item_id: str) -> None:
        self._pix.pop(item_id, None)


class FilterProxy(QSortFilterProxyModel):
    """Поиск + раздел (все/избранное/категория) + сортировка."""

    def __init__(self, model: LibraryModel):
        super().__init__()
        self.lib = model
        self.setSourceModel(model)
        self.setDynamicSortFilter(True)
        self.query = ""
        self.scope = "all"
        self.mode = "added_desc"
        self.sort(0, Qt.SortOrder.AscendingOrder)

    def set_query(self, q: str) -> None:
        self.query = q.casefold().strip()
        self.invalidateFilter()

    def set_scope(self, scope: str) -> None:
        self.scope = scope
        self.invalidateFilter()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.invalidate()

    def filterAcceptsRow(self, row, parent):
        it = self.lib.item_at(row)
        s = self.scope
        if s == "fav" and not it["fav"]:
            return False
        if s.startswith("cat:") and it["cat"] != s[4:]:
            return False
        if self.query:
            hay = (it["title"] + " " + it["cat"]).casefold()
            return all(w in hay for w in self.query.split())
        return True

    def _key(self, it: dict):
        m = self.mode
        if m.startswith("added"):
            return it["added"]
        if m.startswith("title"):
            return natural_key(it["title"])
        if m.startswith("dur"):
            return it["dur"]
        return it["size"]

    def lessThan(self, a, b):
        ia, ib = self.lib.item_at(a.row()), self.lib.item_at(b.row())
        ka, kb = self._key(ia), self._key(ib)
        if ka == kb:
            return ia["id"] < ib["id"]
        less = ka < kb
        return (not less) if self.mode.endswith("_desc") else less

    # --- удобства
    def ids(self) -> List[str]:
        out = []
        for r in range(self.rowCount()):
            out.append(self.lib.item_at(self.mapToSource(self.index(r, 0)).row())["id"])
        return out

    def summary(self) -> Tuple[int, int]:
        n = total = 0
        for r in range(self.rowCount()):
            it = self.lib.item_at(self.mapToSource(self.index(r, 0)).row())
            n += 1
            total += it["dur"]
        return n, total

    def item_id_at(self, proxy_row: int) -> str:
        return self.lib.item_at(self.mapToSource(self.index(proxy_row, 0)).row())["id"]


class QueueModel(QAbstractListModel):
    """Снимок очереди «Далее»: порядок фиксируется в момент запуска видео."""

    def __init__(self, lib: LibraryModel, parent=None):
        super().__init__(parent)
        self.lib = lib
        self.ids: List[str] = []
        self.current = ""

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.ids)

    def set_ids(self, ids: List[str]) -> None:
        self.beginResetModel()
        self.ids = list(ids)
        self.endResetModel()

    def set_current(self, item_id: str) -> None:
        old, self.current = self.current, item_id
        for iid in (old, item_id):
            if iid in self.ids:
                i = self.index(self.ids.index(iid))
                self.dataChanged.emit(i, i)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.ids):
            return None
        iid = self.ids[index.row()]
        it = self.lib.item(iid)
        if it is None:
            return None
        if role == ItemRole:
            return it
        if role == ThumbRole:
            return self.lib.pixmap(iid) if it["th"] else None
        if role == CurrentRole:
            return iid == self.current
        if role == int(Qt.ItemDataRole.DisplayRole):
            return it["title"]
        return None
