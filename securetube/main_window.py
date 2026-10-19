from __future__ import annotations

import os
import shutil
import time
from collections import Counter
from pathlib import Path
from typing import List

from PySide6.QtCore import QByteArray, QEvent, QObject, QPropertyAnimation, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QFrame, QGraphicsOpacityEffect,
                               QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QProgressBar,
                               QPushButton, QStackedWidget, QVBoxLayout, QWidget)

from . import APP_NAME, shortcuts, theme, winutil
from .dialogs import ChangePasswordDialog, LoginDialog, confirm, prompt
from .extensions import ExtError
from .extensions_view import ExtensionsPage
from .icons import icon, logo_pixmap
from .library_view import LibraryPage
from .models import FilterProxy, LibraryModel
from .player_view import PlayerPage
from .settings_view import SettingsPage
from .sitepolicy import SiteError, connect as connect_site, describe_permissions
from .sites_view import SiteDialog, SitesPage
from .sidebar import Sidebar
from .theme import C
from .thumbs import Thumbnailer
from .util import VIDEO_EXTS, fmt_total, scan
from .web_view import HAS_WEB, SiteBrowser
from .widgets import FloatingHost, Toast, icon_button
from .workers import ImportWorker, MissingChecker


class ActivityWatcher(QObject):
    """Любое движение мыши / нажатие клавиши в приложении."""
    activity = Signal()

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress,
                         QEvent.Type.KeyPress, QEvent.Type.Wheel):
            self.activity.emit()
        return False


class ImportBar(QFrame):
    cancelled = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 10, 8)
        lay.setSpacing(14)
        self.label = QLabel("")
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        self.bar.setFixedWidth(220)
        cancel = QPushButton("Отмена")
        cancel.setObjectName("ghost")
        cancel.clicked.connect(self.cancelled)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.bar)
        lay.addWidget(cancel)
        self.hide()


class MainWindow(QMainWindow):
    def __init__(self, core):
        super().__init__()
        self.core, self.s = core, core.settings
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(980, 620)
        self.resize(1280, 800)
        self.setAcceptDrops(True)
        self.locked = False
        self._fullscreen = False
        self._web_fullscreen = False
        self._was_max = False
        self._deco_done = False
        self._controls_visible = False
        self._import_queue: List[Path] = []
        self.worker = None
        self.checker = None
        self._user_rescan = False
        self._fade_anim = None

        self.model = LibraryModel(core, self)
        self.proxy = FilterProxy(self.model)
        self.proxy.set_mode(self.s.get("sort"))
        self.scope = "all"
        self.thumbs = Thumbnailer(self)
        self.thumbs.done.connect(self._thumb_done)

        self._build_ui()
        self.toast = Toast(self)
        self.float_host = FloatingHost()
        self._build_timers()
        self._build_shortcuts()
        self._wire()

        g = str(self.s.get("geometry") or "")
        if g:
            try:
                self.restoreGeometry(QByteArray.fromBase64(g.encode()))
            except Exception:
                pass
        self.sidebar.set_compact(bool(self.s.get("sidebar_compact")), animate=False)
        self.lib_page.view.set_card_size(int(self.s.get("card_size")))
        self.lib_page.set_sort(str(self.s.get("sort")))
        self.idle.set_minutes(int(self.s.get("idle_lock_min")))
        self._update_media_label()
        self.refresh_view()
        self._refresh_ext_page()
        self._refresh_sites_page()

    # ================================================================ UI
    def _build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.topbar = QWidget()
        self.topbar.setFixedHeight(64)
        tb = QHBoxLayout(self.topbar)
        tb.setContentsMargins(12, 8, 18, 8)
        tb.setSpacing(8)
        self.b_menu = icon_button("menu", "Свернуть/развернуть панель (Ctrl+B)")
        self.mark = QLabel()
        self.mark.setPixmap(logo_pixmap(30))
        word = QLabel('<span style="font-weight:800;">Secure</span><span style="font-weight:400;">Tube</span>')
        word.setStyleSheet("font-size:21px;")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по библиотеке")
        self.search.setClearButtonEnabled(True)
        self.search.setMaximumWidth(560)
        self.search.setMinimumWidth(240)
        self.search_action = self.search.addAction(icon("search", C["muted"], 18), QLineEdit.ActionPosition.LeadingPosition)
        self.b_add = QPushButton("＋  Добавить видео")
        self.b_add.setObjectName("primary")
        self.b_add.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_add.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.b_folder = icon_button("folder_plus", "Добавить папку целиком")
        self.b_lock = icon_button("lock", "Заблокировать (Ctrl+L)")
        tb.addWidget(self.b_menu)
        tb.addSpacing(4)
        tb.addWidget(self.mark)
        tb.addWidget(word)
        tb.addStretch(1)
        tb.addWidget(self.search, 100)
        tb.addStretch(1)
        tb.addWidget(self.b_add)
        tb.addWidget(self.b_folder)
        tb.addWidget(self.b_lock)
        root.addWidget(self.topbar)

        self.body = QHBoxLayout()
        self.body.setSpacing(0)
        self.sidebar = Sidebar()
        self.body.addWidget(self.sidebar)
        right = QVBoxLayout()
        right.setSpacing(8)
        self.stack = QStackedWidget()
        self.lib_page = LibraryPage(self.proxy)
        self.player = PlayerPage(self.core, self.model)
        self.settings_page = SettingsPage(self.s)
        self.ext_page = ExtensionsPage()
        self.sites_page = SitesPage()
        self.browser = SiteBrowser()
        for w in (self.lib_page, self.player, self.settings_page, self.ext_page, self.sites_page, self.browser):
            self.stack.addWidget(w)
        self.import_bar = ImportBar()
        right.addWidget(self.stack, 1)
        wrap = QHBoxLayout()
        wrap.setContentsMargins(24, 0, 24, 12)
        wrap.addWidget(self.import_bar)
        self.import_wrap = QWidget()
        self.import_wrap.setLayout(wrap)
        right.addWidget(self.import_wrap)
        self.import_wrap.hide()
        self.body.addLayout(right, 1)
        root.addLayout(self.body, 1)
        self.setCentralWidget(central)

    def _build_timers(self):
        def single(ms, fn):
            t = QTimer(self)
            t.setSingleShot(True)
            t.setInterval(ms)
            t.timeout.connect(fn)
            return t
        self._save_timer = single(700, self._save_now)
        self._refresh_timer = single(60, self.refresh_view)
        self._search_timer = single(150, self._apply_search)
        self._vol_timer = single(500, self._save_volume)
        self._fs_timer = single(2500, self._hide_controls)
        self._vol = (int(self.s.get("volume")), bool(self.s.get("muted")))
        self.idle = IdleLock(self)
        self.idle.expired.connect(self._idle_expired)
        self.watcher = ActivityWatcher(self)
        QApplication.instance().installEventFilter(self.watcher)
        self.watcher.activity.connect(self._on_activity)

    def _build_shortcuts(self):
        def add(seq, fn, player_only=False):
            sc = QShortcut(QKeySequence(seq), self)

            def run():
                if self.locked or self._typing():
                    return
                if player_only and not self._in_player():
                    return
                fn()
            sc.activated.connect(run)
        p = self.player
        for k in ("Space", "K"):
            add(k, p.toggle_play, True)
        add("Left", lambda: p.seek_rel(-5000), True)
        add("Right", lambda: p.seek_rel(5000), True)
        add("J", lambda: p.seek_rel(-10000), True)
        add("L", lambda: p.seek_rel(10000), True)
        add("Up", lambda: p.change_volume(5), True)
        add("Down", lambda: p.change_volume(-5), True)
        add("M", p.toggle_mute, True)
        add("F", self.toggle_fullscreen, True)
        add("Q", p.toggle_queue, True)
        add("N", p.next, True)
        add("P", p.prev, True)
        for d in range(10):
            add(str(d), lambda d=d: p.seek_tenth(d), True)
        add("Esc", self._esc)
        add("Ctrl+L", self.lock)
        add("Ctrl+H", self._toggle_capture)
        add("Ctrl+O", self.add_files_dialog)
        add("Ctrl+F", lambda: (self.search.setFocus(), self.search.selectAll()))
        add("Ctrl+B", self.toggle_sidebar)

    def _wire(self):
        self.b_menu.clicked.connect(self.toggle_sidebar)
        self.b_add.clicked.connect(self.add_files_dialog)
        self.b_folder.clicked.connect(self.add_folder_dialog)
        self.b_lock.clicked.connect(self.lock)
        self.search.textChanged.connect(lambda _: self._search_timer.start())
        sb = self.sidebar
        sb.navigate.connect(self.go)
        sb.addCategory.connect(self.new_category)
        sb.categoryMenu.connect(self.category_menu)
        lp = self.lib_page
        lp.addRequested.connect(self.add_files_dialog)
        lp.sortChanged.connect(self._sort_changed)
        lp.view.clickedId.connect(self.open_video)
        lp.view.contextId.connect(self.card_menu)
        for sig in (self.proxy.rowsInserted, self.proxy.rowsRemoved, self.proxy.modelReset,
                    self.proxy.layoutChanged, self.proxy.dataChanged):
            sig.connect(lambda *a: self._refresh_timer.start())
        pl = self.player
        pl.back.connect(lambda: self.go(self.scope))
        pl.fullscreenToggle.connect(self.toggle_fullscreen)
        pl.itemRequested.connect(self.open_video)
        pl.failed.connect(lambda name, why: self.say(f"«{name}»: {why}", "error"))
        pl.volumeChanged.connect(self._volume_changed)
        pl.durationKnown.connect(self._duration_known)
        pl.positionSaved.connect(self._position_saved)
        st = self.settings_page
        st.changed.connect(self.on_setting)
        st.changePassword.connect(self.change_password)
        st.lockNow.connect(self.lock)
        st.makeShortcut.connect(self.make_shortcut)
        st.chooseMedia.connect(self.choose_media_dir)
        st.resetMedia.connect(self.reset_media_dir)
        st.rescan.connect(lambda: self.rescan(user=True))
        st.clearLibrary.connect(self.clear_library)
        self.import_bar.cancelled.connect(self._cancel_import)
        ep = self.ext_page
        ep.themeChosen.connect(self.choose_theme)
        ep.accentChosen.connect(self.choose_accent)
        ep.installRequested.connect(self.install_extensions)
        ep.openFolder.connect(self.open_ext_folder)
        ep.rescan.connect(lambda: self.rescan_extensions(user=True))
        ep.removeRequested.connect(self.remove_extension)
        sp = self.sites_page
        sp.openSite.connect(self.open_site)
        sp.addRequested.connect(self.add_site)
        sp.editSite.connect(self.edit_site)
        sp.deleteSite.connect(self.delete_site)
        sp.connectRequested.connect(self.connect_catalog)
        br = self.browser
        br.closeRequested.connect(lambda: self.go("sites"))
        br.allowDomain.connect(self.allow_site_domain)
        br.externalRequested.connect(self.open_external)
        br.clearRequested.connect(self.clear_site_data)
        br.fullscreenChanged.connect(self._web_fs)
        theme.on_change(self.retheme)

    # ================================================================ служебное
    def say(self, text: str, kind: str = "info"):
        self.toast.capture_hidden = bool(self.s.get("hide_from_capture"))
        self.toast.lift = 190 if self._fullscreen else 96
        self.toast.show_message(text, kind)

    def _typing(self) -> bool:
        w = QApplication.focusWidget()
        return isinstance(w, QLineEdit)

    def _in_player(self) -> bool:
        return self.stack.currentWidget() is self.player

    def mark_dirty(self):
        self._save_timer.start()

    def _save_now(self):
        try:
            self.core.library.save()
        except OSError as e:
            self.say(f"Не удалось сохранить библиотеку: {e.strerror or e}", "error")

    def _set(self, key, value):
        try:
            self.s.set(key, value)
        except OSError as e:
            self.say(f"Не удалось сохранить настройки: {e.strerror or e}", "error")

    # ================================================================ вид
    def refresh_sidebar(self):
        items = self.core.library.items.values()
        cnt = Counter(i["cat"] for i in items if i["cat"])
        self.sidebar.set_counts(len(self.core.library.items), sum(1 for i in items if i["fav"]))
        self.sidebar.set_categories([(c, cnt.get(c, 0)) for c in self.core.library.categories],
                                    self.scope)

    def refresh_view(self):
        if self.scope.startswith("cat:") and self.scope[4:] not in self.core.library.categories:
            self.scope = "all"
            self.proxy.set_scope("all")
        n, total = self.proxy.summary()
        title = {"all": "Все видео", "fav": "Избранное"}.get(self.scope) or self.scope[4:]
        summary = (f"{n} видео" + (f", {fmt_total(total)}" if total > 0 else "")) if n else ""
        self.lib_page.refresh(title, self.scope, len(self.core.library.items), summary, n)
        self.refresh_sidebar()
        if self.stack.currentWidget() is self.settings_page:
            self.sidebar.select("settings")
        elif self.stack.currentWidget() is self.ext_page:
            self.sidebar.select("ext")
        elif self.stack.currentWidget() in (self.sites_page, self.browser):
            self.sidebar.select("sites")

    def _fade(self, w: QWidget):
        eff = QGraphicsOpacityEffect(w)
        w.setGraphicsEffect(eff)
        a = QPropertyAnimation(eff, b"opacity", w)
        a.setDuration(180)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.finished.connect(lambda: w.setGraphicsEffect(None))
        a.start()
        self._fade_anim = a

    def _show_page(self, w: QWidget, fade: bool = True):
        cur = self.stack.currentWidget()
        if cur is self.player and w is not self.player:
            self.player.stop()
        if cur is self.browser and w is not self.browser:
            self._web_fs(False)
            self.browser.close_site()
        if cur is not w:
            self.stack.setCurrentWidget(w)
            if fade and w is not self.player:
                self._fade(w)

    def go(self, key: str):
        if self._fullscreen:
            self._exit_fs()
        if key in ("settings", "ext", "sites"):
            self._show_page({"settings": self.settings_page, "ext": self.ext_page, "sites": self.sites_page}[key])
            self.sidebar.select(key)
            return
        self.scope = key
        self.proxy.set_scope(key)
        self._show_page(self.lib_page)
        self.refresh_view()
        self.sidebar.select(key)

    def toggle_sidebar(self):
        if self._fullscreen:
            return
        on = not self.sidebar.compact
        self.sidebar.set_compact(on)
        self._set("sidebar_compact", on)

    def _apply_search(self):
        self.proxy.set_query(self.search.text())
        if self._in_player() or self.stack.currentWidget() in (self.settings_page, self.ext_page, self.sites_page, self.browser):
            self.go(self.scope)

    def _sort_changed(self, mode: str):
        self.proxy.set_mode(mode)
        self._set("sort", mode)

    def open_video(self, item_id: str):
        if not item_id or self.locked:
            return
        ids = self.proxy.ids() if not self._in_player() else (self.player.queue.ids or self.proxy.ids())
        if item_id not in ids:
            ids = [item_id]
        if self.player.play_item(item_id, ids):
            self._show_page(self.player, fade=False)
            self.player.setFocus()

    def _volume_changed(self, v: int, muted: bool):
        self._vol = (v, muted)
        self._vol_timer.start()

    def _save_volume(self):
        v, m = self._vol
        try:
            self.s.set("volume", v, save=False)
            self.s.set("muted", m, save=False)
            self.s.save()
        except OSError:
            pass

    def _duration_known(self, iid: str, d: int):
        self.model.changed(iid)
        self.mark_dirty()

    def _position_saved(self, iid: str, pos: int):
        it = self.model.item(iid)
        if it and it["pos"] != pos:
            it["pos"] = pos
            self.mark_dirty()

    def toggle_fullscreen(self):
        if not self._in_player():
            return
        if self._fullscreen:
            self._exit_fs()
        else:
            self._enter_fs()

    def _enter_fs(self):
        self._fullscreen = True
        self._was_max = self.isMaximized()
        self.topbar.hide()
        self.sidebar.hide()
        self.import_wrap.hide()
        self.player.enter_fullscreen(self.float_host)
        self.showFullScreen()
        self._reveal_controls()

    def _exit_fs(self):
        self._fullscreen = False
        self._fs_timer.stop()
        self._controls_visible = False
        self.float_host.hide_now()
        self.player.exit_fullscreen(self.float_host)
        self.topbar.show()
        self.sidebar.show()
        self.import_wrap.setVisible(bool(self.worker and self.worker.isRunning()))
        if self._was_max:
            self.showMaximized()
        else:
            self.showNormal()

    def _reveal_controls(self):
        self.float_host.capture_hidden = bool(self.s.get("hide_from_capture"))
        self.float_host.reveal(self.screen().geometry())
        self.player.set_cursor_hidden(False)
        self._controls_visible = True
        self._fs_timer.start()

    def _hide_controls(self):
        if not self._fullscreen:
            return
        if self.player.bar.dragging() or self.float_host.underMouse():
            self._fs_timer.start()
            return
        self.float_host.conceal()
        self._controls_visible = False
        self.player.set_cursor_hidden(True)

    def _on_activity(self):
        self.idle.poke()
        if self._fullscreen:
            if self._controls_visible:
                self._fs_timer.start()
            else:
                self._reveal_controls()

    def _esc(self):
        if self._fullscreen:
            self._exit_fs()
        elif self.search.hasFocus() and self.search.text():
            self.search.clear()
        elif self._in_player():
            self.go(self.scope)

    def add_files_dialog(self):
        if self.locked:
            return
        exts = " ".join("*" + e for e in sorted(VIDEO_EXTS))
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите видео", "", f"Видео ({exts});;Все файлы (*.*)")
        if files:
            self.start_import(files)

    def add_folder_dialog(self):
        if self.locked:
            return
        d = QFileDialog.getExistingDirectory(self, "Выберите папку с видео")
        if d:
            self.start_import([d])

    def start_import(self, raw_paths):
        files = scan(raw_paths)
        if not files:
            self.say("Видео не найдены. Поддерживаются MP4, MKV, WebM, MOV, AVI и другие распространённые форматы.", "error")
            return
        if self.worker and self.worker.isRunning():
            self._import_queue.extend(files)
            self.say(f"Добавлено в очередь: {len(files)}")
            return
        self._run_import(files)

    def _run_import(self, files: List[Path]):
        mode = str(self.s.get("storage_mode"))
        self._imp = {"ok": 0, "skip": 0, "fail": []}
        self.worker = ImportWorker(files, self.core.library.orig_set(), mode, self.core.media_dir(),
                                   bool(self.s.get("delete_originals")) and mode == "copy", self)
        w = self.worker
        w.progress.connect(self._import_progress)
        w.imported.connect(self._imported)
        w.skipped.connect(lambda n: self._imp.__setitem__("skip", self._imp["skip"] + 1))
        w.failed.connect(lambda n, why: self._imp["fail"].append((n, why)))
        w.finished.connect(self._import_done)
        self.import_bar.bar.setValue(0)
        self.import_bar.label.setText("Подготовка…")
        self.import_bar.show()
        if not self._fullscreen:
            self.import_wrap.show()
        w.start()

    def _import_progress(self, n: int, total: int, name: str, frac: float):
        shown = name if len(name) <= 48 else name[:45] + "…"
        self.import_bar.label.setText(f"Добавляю {n} из {total}: {shown}")
        self.import_bar.bar.setValue(int((n - 1 + frac) / max(1, total) * 1000))

    def _imported(self, item: dict):
        if self.scope.startswith("cat:"):
            item["cat"] = self.scope[4:]
        self.model.add_item(item)
        self._imp["ok"] += 1
        self.mark_dirty()
        self.thumbs.enqueue(item["id"], item["path"])

    def _cancel_import(self):
        self._import_queue.clear()
        if self.worker:
            self.worker.cancel()

    def _import_done(self):
        self.worker = None
        self.import_wrap.hide()
        self._save_now()
        r = self._imp
        parts = []
        if r["ok"]:
            parts.append(f"Добавлено видео: {r['ok']}")
        if r["skip"]:
            parts.append(f"уже в библиотеке: {r['skip']}")
        if r["fail"]:
            n, why = r["fail"][0]
            more = f" (и ещё {len(r['fail']) - 1})" if len(r["fail"]) > 1 else ""
            self.say(f"Не удалось добавить «{n}»: {why}{more}", "error")
        elif parts:
            self.say(", ".join(parts), "ok" if r["ok"] else "info")
        if self._import_queue:
            nxt, self._import_queue = self._import_queue, []
            self._run_import(nxt)

    def dragEnterEvent(self, e):
        if not self.locked and e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths and not self.locked:
            e.acceptProposedAction()
            self.start_import(paths)

    def _thumb_done(self, iid: str, jpeg, dur: int):
        it = self.model.item(iid)
        if not it:
            return
        if dur > 0:
            it["dur"] = int(dur)
        if jpeg:
            try:
                self.core.thumbs.save(iid, jpeg)
                it["th"], it["tf"] = True, 0
                self.model.drop_pixmap(iid)
            except OSError:
                it["tf"] += 1
        else:
            it["tf"] += 1
        self.model.changed(iid)
        self.mark_dirty()

    def _queue_missing_thumbs(self):
        for it in list(self.core.library.items.values()):
            if (not it["th"] or it["dur"] <= 0) and it["tf"] < 2:
                self.thumbs.enqueue(it["id"], it["path"])

    def card_menu(self, iid: str, pos):
        it = self.model.item(iid)
        if not it:
            return
        m = QMenu(self)
        m.addAction(icon("play", C["text"], 18), "Смотреть").triggered.connect(lambda: self.open_video(iid))
        fav = it["fav"]
        m.addAction(icon("star_f" if fav else "star", C["text"], 18),
                    "Убрать из избранного" if fav else "В избранное").triggered.connect(lambda: self.toggle_fav(iid))
        cm = m.addMenu(icon("tag", C["text"], 18), "Категория")
        a = cm.addAction("Без категории")
        a.setCheckable(True)
        a.setChecked(not it["cat"])
        a.triggered.connect(lambda: self.set_category(iid, ""))
        for c in self.core.library.categories:
            a = cm.addAction(c)
            a.setCheckable(True)
            a.setChecked(it["cat"] == c)
            a.triggered.connect(lambda _=False, c=c: self.set_category(iid, c))
        cm.addSeparator()
        cm.addAction(icon("plus", C["text"], 16), "Новая категория…").triggered.connect(lambda: self.set_category_new(iid))
        m.addAction(icon("edit", C["text"], 18), "Переименовать…").triggered.connect(lambda: self.rename_item(iid))
        m.addSeparator()
        m.addAction(icon("trash", C["danger"], 18), "Удалить из библиотеки…").triggered.connect(lambda: self.delete_item(iid))
        m.exec(pos)

    def toggle_fav(self, iid: str):
        it = self.model.item(iid)
        if it:
            it["fav"] = not it["fav"]
            self.model.changed(iid)
            self.proxy.invalidateFilter()
            self.mark_dirty()

    def set_category(self, iid: str, cat: str):
        it = self.model.item(iid)
        if it:
            it["cat"] = cat
            self.model.changed(iid)
            self.proxy.invalidateFilter()
            self.mark_dirty()

    def set_category_new(self, iid: str):
        name = self._new_category_name()
        if name:
            self.set_category(iid, name)

    def rename_item(self, iid: str):
        it = self.model.item(iid)
        if not it:
            return
        name = prompt(self, "Переименовать", "Название видео", it["title"], ok="Сохранить")
        if name:
            it["title"] = name[:120]
            self.model.changed(iid)
            self.proxy.invalidate()
            self.mark_dirty()

    def delete_item(self, iid: str):
        it = self.model.item(iid)
        if not it:
            return
        extra = ("Копия файла в библиотеке будет удалена." if it["owned"]
                 else "Исходный файл на диске останется на месте.")
        if not confirm(self, f"Удалить «{it['title']}»?", f"Видео исчезнет из библиотеки. {extra}"):
            return
        if self._in_player() and self.player.cur == iid:
            self.go(self.scope)
        self.thumbs.cancel(iid)
        if it["owned"]:
            try:
                os.remove(it["path"])
            except OSError:
                pass
        self.core.thumbs.delete(iid)
        self.model.remove_item(iid)
        self.mark_dirty()

    def _new_category_name(self):
        name = prompt(self, "Новая категория", "Название категории", ok="Создать")
        if not name:
            return None
        created = self.core.library.add_category(name)
        if not created:
            self.say("Такая категория уже есть.", "error")
            for c in self.core.library.categories:
                if c.casefold() == name.casefold():
                    return c
            return None
        self.mark_dirty()
        self.refresh_sidebar()
        return created

    def new_category(self):
        self._new_category_name()

    def category_menu(self, name: str, pos):
        m = QMenu(self)
        m.addAction(icon("edit", C["text"], 18), "Переименовать…").triggered.connect(lambda: self.rename_category(name))
        m.addAction(icon("trash", C["danger"], 18), "Удалить категорию…").triggered.connect(lambda: self.delete_category(name))
        m.exec(pos)

    def rename_category(self, name: str):
        new = prompt(self, "Переименовать категорию", "Название категории", name, ok="Сохранить")
        if not new:
            return
        res = self.core.library.rename_category(name, new)
        if not res:
            self.say("Не получилось: такое название уже занято.", "error")
            return
        if self.scope == "cat:" + name:
            self.scope = "cat:" + res
            self.proxy.set_scope(self.scope)
        self.proxy.invalidate()
        self.mark_dirty()
        self.refresh_view()

    def delete_category(self, name: str):
        if not confirm(self, f"Удалить категорию «{name}»?", "Видео останутся в библиотеке, просто без категории."):
            return
        self.core.library.delete_category(name)
        self.proxy.invalidate()
        self.mark_dirty()
        self.refresh_view()

    def on_setting(self, key: str, value):
        self._set(key, value)
        if key == "card_size":
            self.lib_page.view.set_card_size(int(value))
        elif key == "idle_lock_min":
            self.idle.set_minutes(int(value))
        elif key == "hide_from_capture":
            self.apply_capture()

    def _toggle_capture(self):
        new = not bool(self.s.get("hide_from_capture"))
        self._set("hide_from_capture", new)
        self.settings_page.sync()
        self.apply_capture()
        self.say("Окно скрыто от захвата экрана" if new else "Захват экрана снова разрешён")

    def apply_capture(self):
        flag = bool(self.s.get("hide_from_capture"))
        winutil.capture_hidden(int(self.winId()), flag)
        self.toast.capture_hidden = flag
        self.float_host.capture_hidden = flag
        if self.float_host.isVisible():
            winutil.capture_hidden(int(self.float_host.winId()), flag)

    def change_password(self):
        if ChangePasswordDialog(self.core.auth, self).exec() == QDialog.DialogCode.Accepted:
            self.say("Пароль изменён", "ok")

    def make_shortcut(self):
        ok, msg = shortcuts.create_shortcuts()
        self.say(msg, "ok" if ok else "error")

    def _update_media_label(self):
        custom = str(self.s.get("media_dir") or "")
        if not custom:
            self.settings_page.set_media_text("Стандартная (скрытая)")
        else:
            txt = custom if len(custom) <= 36 else "…" + custom[-35:]
            self.settings_page.set_media_text(txt)

    def choose_media_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Папка для видео библиотеки")
        if not d:
            return
        probe = Path(d) / f".xt{os.getpid()}.tmp"
        try:
            probe.write_bytes(b"x")
            probe.unlink()
        except OSError:
            self.say("В эту папку нельзя записывать. Выберите другую.", "error")
            return
        self._set("media_dir", d)
        self._update_media_label()
        self.say("Новые видео будут копироваться в выбранную папку", "ok")

    def reset_media_dir(self):
        self._set("media_dir", "")
        self._update_media_label()

    def rescan(self, user: bool = False):
        self._user_rescan = user
        orphans = self.core.library.adopt_orphans(self.core.media_dir())
        if orphans:
            self.model.reset_all()
            self.mark_dirty()
            for it in orphans:
                self.thumbs.enqueue(it["id"], it["path"])
            self.say(f"Найдено потерянных видео: {len(orphans)} — они возвращены в библиотеку", "ok")
        if self.checker and self.checker.isRunning():
            return
        pairs = [(i["id"], i["path"]) for i in self.core.library.items.values()]
        self.checker = MissingChecker(pairs, self)
        self.checker.result.connect(self._missing_result)
        self.checker.start()

    def _missing_result(self, ids):
        self.model.set_missing(set(ids))
        if self._user_rescan:
            self.say(f"Файлов не найдено: {len(ids)}" if ids else "Проверка завершена: всё на месте", "error" if ids else "ok")
        self._user_rescan = False

    def clear_library(self):
        if not self.core.library.items:
            self.say("Библиотека и так пуста")
            return
        if not confirm(self, "Очистить библиотеку?",
                       "Все видео будут удалены из библиотеки. Копии в скрытой папке программы удалятся, "
                       "исходные файлы на диске не затрагиваются. Это нельзя отменить.", ok="Очистить"):
            return
        self.go("all")
        for it in list(self.core.library.items.values()):
            self.thumbs.cancel(it["id"])
            if it["owned"]:
                try:
                    os.remove(it["path"])
                except OSError:
                    pass
            self.core.thumbs.delete(it["id"])
        self.core.library.items.clear()
        self.model.reset_all()
        self._save_now()
        self.say("Библиотека очищена", "ok")

    def _refresh_ext_page(self):
        self.ext_page.refresh(self.core.ext, self.core.ext.theme(str(self.s.get("theme"))).id, str(self.s.get("accent")))

    def retheme(self):
        theme.decorate(int(self.winId()))
        self.search_action.setIcon(icon("search", C["muted"], 18))
        self.mark.setPixmap(logo_pixmap(30))
        self.lib_page.retheme()
        self.player.bar.refresh_icons()
        for w in self.findChildren(QWidget):
            w.update()

    def _apply_theme(self, theme_id: str, accent_id: str):
        ext = self.core.ext
        t = ext.theme(theme_id)
        theme.apply(t, ext.accent(accent_id))
        self._set("theme", t.id)
        self._set("accent", accent_id if ext.accent(accent_id) else "")
        self._refresh_ext_page()
        return t

    def choose_theme(self, theme_id: str):
        t = self._apply_theme(theme_id, str(self.s.get("accent")))
        self.say(f"Тема «{t.name}»", "ok")

    def choose_accent(self, accent_id: str):
        self._apply_theme(str(self.s.get("theme")), accent_id)

    def install_extensions(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Выберите файлы расширений", "",
                                                "Расширения (*.json *.xtheme);;Все файлы (*.*)")
        if not files:
            return
        before = set(self.core.ext.themes)
        done, errors = [], []
        for f in files:
            try:
                done += self.core.ext.install_file(Path(f))
            except ExtError as e:
                errors.append(f"{Path(f).name}: {e}")
        new = [i for i in self.core.ext.themes if i not in before]
        if len(new) == 1:                       
            self._apply_theme(new[0], str(self.s.get("accent")))
        else:
            self._refresh_ext_page()
        if errors:
            self.say(errors[0] + (f" (и ещё {len(errors) - 1})" if len(errors) > 1 else ""), "error")
        elif done:
            self.say("Установлено: " + ", ".join(done[:3]) + (f" и ещё {len(done) - 3}" if len(done) > 3 else ""), "ok")

    def open_ext_folder(self):
        d = self.core.ext.user_dir
        try:
            (d / "themes").mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.say(f"Не удалось создать папку: {e.strerror or e}", "error")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(d)))

    def rescan_extensions(self, user: bool = False):
        self.core.ext.scan()
        t = self.core.ext.theme(str(self.s.get("theme")))
        self._apply_theme(t.id, str(self.s.get("accent")))
        if user:
            n = len(self.core.ext.errors)
            self.say(f"Список обновлён. Тем: {len(self.core.ext.themes)}" + (f", с ошибками файлов: {n}" if n else ""),
                     "error" if n else "ok")

    def remove_extension(self, kind: str, item_id: str):
        item = self.core.ext.themes.get(item_id) if kind == "theme" else self.core.ext.accents.get(item_id)
        if not item:
            return
        if not confirm(self, f"Удалить «{item.name}»?", "Файл расширения будет удалён с диска."):
            return
        was_active = (kind == "theme" and str(self.s.get("theme")) == item_id)
        if not self.core.ext.remove(kind, item_id):
            self.say("Не удалось удалить файл расширения", "error")
            return
        self._apply_theme(self.core.ext.theme(str(self.s.get("theme"))).id if not was_active else "securetube",
                          str(self.s.get("accent")))

    def _refresh_sites_page(self):
        book = self.core.sites
        self.sites_page.refresh(list(book.sites.values()), self.core.ext.catalog_sites(), book.connected_sources(), HAS_WEB)

    def _save_sites(self) -> bool:
        try:
            self.core.sites.save()
            return True
        except OSError as e:
            self.say(f"Не удалось сохранить список сайтов: {e.strerror or e}", "error")
            return False

    def _store_site(self, site) -> bool:
        try:
            self.core.sites.add(site)
        except SiteError as e:
            self.say(str(e), "error")
            return False
        ok = self._save_sites()
        self._refresh_sites_page()
        return ok

    def add_site(self):
        dlg = SiteDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_site:
            dlg.result_site.added = time.time()
            if self._store_site(dlg.result_site):
                self.say(f"Сайт «{dlg.result_site.name}» добавлен", "ok")

    def edit_site(self, site_id: str):
        old = self.core.sites.get(site_id)
        if not old:
            return
        dlg = SiteDialog(self, old)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.result_site:
            self._store_site(dlg.result_site)

    def _forget_site_data(self, site_id: str):
        shutil.rmtree(self.core.root / "web" / site_id, ignore_errors=True)

    def delete_site(self, site_id: str):
        site = self.core.sites.get(site_id)
        if not site:
            return
        if not confirm(self, f"Удалить сайт «{site.name}»?", "Сайт и все его сохранённые данные будут удалены."):
            return
        if self.browser.site and self.browser.site.id == site_id:
            self.go("sites")
        self.core.sites.remove(site_id)
        self._save_sites()
        QTimer.singleShot(600, lambda: self._forget_site_data(site_id))
        self._refresh_sites_page()

    def connect_catalog(self, catalog_id: str):
        manifest = self.core.ext.sites.get(catalog_id)
        if not manifest:
            return
        if catalog_id in self.core.sites.connected_sources():
            self.say("Этот сайт уже подключён")
            return
        rights = "\n".join("• " + line for line in describe_permissions(manifest))
        if not confirm(self, f"Подключить «{manifest.name}»?", "Сайт получит только эти права:\n" + rights, ok="Подключить"):
            return
        if self._store_site(connect_site(manifest)):
            self.say(f"«{manifest.name}» подключён: он появился в разделе «Мои сайты»", "ok")

    def open_site(self, site_id: str):
        if self.locked:
            return
        if not HAS_WEB:
            self.say("Нужен компонент QtWebEngine: выполните pip install -U PySide6 и перезапустите программу", "error")
            return
        site = self.core.sites.get(site_id)
        if not site:
            return
        self.player.pause()
        storage = (self.core.root / "web" / site.id) if site.persist else None
        self.browser.open_site(site, storage)
        self._show_page(self.browser, fade=False)
        self.sidebar.select("sites")

    def allow_site_domain(self, site_id: str, host: str):
        try:
            site = self.core.sites.add_allow(site_id, host)
        except (SiteError, KeyError) as e:
            self.say(str(e) if isinstance(e, SiteError) else "Сайт не найден", "error")
            return
        self._save_sites()
        self.browser.refresh_allow(site)
        self._refresh_sites_page()
        self.say(f"Домен {host} разрешён для «{site.name}»", "ok")

    def open_external(self, url: str):
        if not url.startswith("https://"):
            return
        if confirm(self, "Открыть во внешнем браузере?", f"{url}\n\nСтраница откроется в обычном браузере уже вне защиты SecureTube.", ok="Открыть"):
            QDesktopServices.openUrl(QUrl(url))

    def clear_site_data(self, site_id: str):
        if not confirm(self, "Очистить данные сайта?", "Cookie, кэш и сохранённый вход будут удалены, сайт откроется заново.", ok="Очистить"):
            return
        self.browser.close_site()
        QTimer.singleShot(700, lambda: (self._forget_site_data(site_id), self.open_site(site_id)))

    def _web_fs(self, on: bool):
        """Полный экран из самой страницы (видео): прячем всё лишнее."""
        if on == self._web_fullscreen:
            return
        self._web_fullscreen = on
        self.topbar.setVisible(not on)
        self.sidebar.setVisible(not on)
        if on:
            self._was_max = self.isMaximized()
            self.showFullScreen()
        else:
            self.showMaximized() if self._was_max else self.showNormal()

    def report_status(self, st: dict):
        lib, cfg = st.get("library"), st.get("settings")
        if lib == "recovered":
            self.say("Библиотека восстановлена из резервной копии", "info")
        elif lib == "corrupt":
            self.say("Файл библиотеки повреждён, начата новая. Потерянные видео можно вернуть: "
                     "Настройки → Проверка библиотеки.", "error")
            self.rescan()
        elif st.get("sites") == "corrupt":
            self.say("Список сайтов был повреждён и очищен", "error")
        elif cfg == "corrupt":
            self.say("Настройки были повреждены и сброшены к стандартным", "error")
        self.sidebar.set_compact(bool(self.s.get("sidebar_compact")), animate=False)
        self.settings_page.sync()
        self._update_media_label()

    def startup_tasks(self):
        self._queue_missing_thumbs()
        pairs = [(i["id"], i["path"]) for i in self.core.library.items.values()]
        self.checker = MissingChecker(pairs, self)
        self.checker.result.connect(self._missing_result)
        self.checker.start()

    def _idle_expired(self):
        if self.locked:
            return
        if self.player.is_playing():
            self.idle.poke()
        else:
            self.lock()

    def lock(self):
        if self.locked:
            return
        self.locked = True
        self.player.pause()
        self._web_fs(False)
        self.browser.close_site()
        if self._fullscreen:
            self._exit_fs()
        self.toast.hide_now()
        self.float_host.hide_now()
        self.idle.stop()
        was_max = self.isMaximized()
        self.hide()
        dlg = LoginDialog(self.core.auth)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        if not ok:
            self.locked = False
            self._quit()
            return
        self.locked = False
        self.idle.poke()
        self.showMaximized() if was_max else self.showNormal()
        self.raise_()
        self.activateWindow()

    def bring_to_front(self):
        if self.locked:
            return
        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()

    def changeEvent(self, e):
        if (e.type() == QEvent.Type.WindowStateChange and self.isMinimized() and not self.locked
                and self.s.get("lock_on_minimize")):
            QTimer.singleShot(0, self.lock)
        super().changeEvent(e)

    def showEvent(self, e):
        super().showEvent(e)
        if not self._deco_done:
            self._deco_done = True
            theme.decorate(int(self.winId()))
            self.apply_capture()

    def _quit(self):
        self.close()

    def closeEvent(self, e):
        self.browser.close_site()
        self.float_host.hide_now()
        self.toast.hide_now()
        self.player.stop()
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)
        if self.checker and self.checker.isRunning():
            self.checker.wait(1000)
        self._save_volume()
        if not self._fullscreen and not self.isMinimized():
            try:
                self.s.set("geometry", bytes(self.saveGeometry().toBase64().data()).decode(), save=False)
                self.s.save()
            except OSError:
                pass
        self._save_now()
        e.accept()
        QApplication.quit()


class IdleLock(QObject):
    expired = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._t = QTimer(self)
        self._t.setSingleShot(True)
        self._t.timeout.connect(self.expired)
        self._ms = 0

    def set_minutes(self, m: int):
        self._ms = m * 60000
        self.poke()

    def poke(self):
        if self._ms > 0:
            self._t.start(self._ms)
        else:
            self._t.stop()

    def stop(self):
        self._t.stop()
