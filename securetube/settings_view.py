from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout,
                               QWidget)

from . import APP_NAME, APP_VERSION
from .widgets import Segmented, Switch, hline


class SettingsPage(QScrollArea):
    changed = Signal(str, object)
    changePassword = Signal()
    lockNow = Signal()
    makeShortcut = Signal()
    chooseMedia = Signal()
    resetMedia = Signal()
    rescan = Signal()
    clearLibrary = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        host = QWidget()
        outer = QHBoxLayout(host)
        outer.setContentsMargins(24, 18, 24, 32)
        col_w = QWidget()
        col_w.setMaximumWidth(780)
        self.col = QVBoxLayout(col_w)
        self.col.setContentsMargins(0, 0, 0, 0)
        self.col.setSpacing(14)
        outer.addStretch(1)
        outer.addWidget(col_w, 100)
        outer.addStretch(1)
        self.setWidget(host)
        self._ctl: dict = {}

        h = QLabel("Настройки")
        h.setObjectName("h1")
        self.col.addWidget(h)

        c = self._card("Видео и библиотека")
        self._ctl["storage_mode"] = self._seg("storage_mode", [("copy", "Копировать"), ("link", "Не копировать")])
        self._row(c, "Как добавлять видео", "Копия хранится в скрытой папке программы и не зависит от исходного файла. "
                  "«Не копировать» — только ссылка: быстро и без лишнего места на диске.", self._ctl["storage_mode"])
        self._ctl["delete_originals"] = self._sw("delete_originals")
        self._row(c, "Удалять оригинал после копирования", "Освобождает место: исходный файл удаляется, "
                  "когда копия в библиотеке готова.", self._ctl["delete_originals"])
        self.media_label = QLabel("")
        self.media_label.setObjectName("muted")
        b1, b2 = QPushButton("Выбрать…"), QPushButton("Сбросить")
        b1.clicked.connect(self.chooseMedia)
        b2.clicked.connect(self.resetMedia)
        box = QWidget()
        bl = QHBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.addWidget(self.media_label)
        bl.addWidget(b1)
        bl.addWidget(b2)
        self._row(c, "Папка для видео", "Только для новых видео. Уже добавленные остаются на месте.", box)
        b3 = QPushButton("Проверить")
        b3.clicked.connect(self.rescan)
        self._row(c, "Проверка библиотеки", "Найдёт видео, чьи файлы пропали, и вернёт потерянные копии.", b3, last=True)

        c = self._card("Вид и просмотр")
        self._ctl["card_size"] = self._seg("card_size", [(0, "Мелкие"), (1, "Средние"), (2, "Крупные")])
        self._row(c, "Размер карточек", "", self._ctl["card_size"])
        self._ctl["autoplay_next"] = self._sw("autoplay_next")
        self._row(c, "Автопереход к следующему", "Когда видео закончилось, включается следующее из списка.", self._ctl["autoplay_next"])
        self._ctl["remember_position"] = self._sw("remember_position")
        self._row(c, "Продолжать с места остановки", "Выключено — программа не запоминает, что и до какого момента вы смотрели.",
                  self._ctl["remember_position"], last=True)

        c = self._card("Безопасность")
        b4 = QPushButton("Сменить…")
        b4.clicked.connect(self.changePassword)
        self._row(c, "Пароль", f"Не короче 8 символов. После трёх неверных попыток вход блокируется на 24 часа.", b4)
        self._ctl["lock_on_minimize"] = self._sw("lock_on_minimize")
        self._row(c, "Блокировать при сворачивании", "Видео встаёт на паузу, окно скрывается, нужен пароль.", self._ctl["lock_on_minimize"])
        self._ctl["idle_lock_min"] = self._seg("idle_lock_min", [(0, "Выкл"), (1, "1 мин"), (5, "5 мин"), (15, "15 мин")])
        self._row(c, "Блокировка при бездействии", "Срабатывает, когда видео на паузе и вы ничего не делаете.", self._ctl["idle_lock_min"])
        self._ctl["hide_from_capture"] = self._sw("hide_from_capture")
        self._row(c, "Скрывать окно от захвата экрана", "Окно не попадает в скриншоты и демонстрацию экрана (Ctrl+H).",
                  self._ctl["hide_from_capture"])
        b5 = QPushButton("Заблокировать")
        b5.clicked.connect(self.lockNow)
        self._row(c, "Заблокировать сейчас", "Ctrl+L", b5, last=True)

        c = self._card("Приложение")
        b6 = QPushButton("Создать ярлык")
        b6.clicked.connect(self.makeShortcut)
        self._row(c, "Ярлык на рабочем столе", "Запуск в один клик, значок SecureTube.", b6)
        b7 = QPushButton("Очистить…")
        b7.setObjectName("danger")
        b7.clicked.connect(self.clearLibrary)
        self._row(c, "Очистить библиотеку", "Удаляет все видео из библиотеки; копии в скрытой папке удаляются, "
                  "исходные файлы не затрагиваются.", b7)
        about = QLabel(f"{APP_NAME} {APP_VERSION}. Видео, превью и настройки хранятся только на этом компьютере, "
                       "без аккаунтов, рекламы и интернета.")
        about.setObjectName("muted")
        about.setWordWrap(True)
        c.addWidget(about)
        self.col.addStretch(1)
        self.sync()

    def _card(self, title: str) -> QVBoxLayout:
        f = QFrame()
        f.setObjectName("card")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(12)
        t = QLabel(title)
        t.setObjectName("h2")
        lay.addWidget(t)
        self.col.addWidget(f)
        return lay

    def _row(self, card: QVBoxLayout, title: str, desc: str, ctl: QWidget, last: bool = False) -> None:
        row = QHBoxLayout()
        row.setSpacing(18)
        left = QVBoxLayout()
        left.setSpacing(2)
        left.addWidget(QLabel(title))
        if desc:
            d = QLabel(desc)
            d.setObjectName("muted")
            d.setWordWrap(True)
            left.addWidget(d)
        row.addLayout(left, 1)
        row.addWidget(ctl, 0, Qt.AlignmentFlag.AlignVCenter)
        card.addLayout(row)
        if not last:
            card.addWidget(hline())

    def _sw(self, key: str) -> Switch:
        s = Switch()
        s.clicked.connect(lambda _=False, k=key, w=s: self._emit(k, w.isChecked()))
        return s

    def _seg(self, key: str, options) -> Segmented:
        s = Segmented(options)
        s.changed.connect(lambda v, k=key: self._emit(k, v))
        return s

    def _emit(self, key: str, value) -> None:
        self.changed.emit(key, value)
        self._update_enabled()

    # --- синхронизация со значениями
    def sync(self) -> None:
        for key, w in self._ctl.items():
            v = self.settings.get(key)
            if isinstance(w, Switch):
                w.setChecked(bool(v))
            else:
                w.setValue(v)
        self._update_enabled()

    def _update_enabled(self) -> None:
        copy_mode = self._ctl["storage_mode"].value() == "copy"
        self._ctl["delete_originals"].setEnabled(copy_mode)

    def set_media_text(self, text: str) -> None:
        self.media_label.setText(text)
