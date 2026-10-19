from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QPoint, Qt, QTimer, QUrl, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMenu, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget)

from .icons import icon
from .sitepolicy import HARD_BLOCK, REASONS, Site, decide
from .theme import C
from .widgets import icon_button

try:
    from PySide6.QtWebEngineCore import (QWebEnginePage, QWebEngineProfile, QWebEngineSettings,
                                         QWebEngineUrlRequestInfo, QWebEngineUrlRequestInterceptor)
    from PySide6.QtWebEngineWidgets import QWebEngineView
    HAS_WEB = True
except Exception:                       
    HAS_WEB = False

SETTINGS_OFF = ("PluginsEnabled", "JavascriptCanOpenWindows", "JavascriptCanAccessClipboard", "JavascriptCanPaste",
                "AllowRunningInsecureContent", "AllowGeolocationOnInsecureOrigins", "LocalContentCanAccessRemoteUrls",
                "LocalContentCanAccessFileUrls", "ScreenCaptureEnabled", "HyperlinkAuditingEnabled", "DnsPrefetchEnabled",
                "WebGLEnabled", "AutoLoadIconsForPage", "TouchIconsEnabled", "NavigateOnDropEnabled")
SETTINGS_ON = ("WebRTCPublicInterfacesOnly", "PlaybackRequiresUserGesture", "ErrorPageEnabled", "LocalStorageEnabled",
               "ScrollAnimatorEnabled")


if HAS_WEB:
    _RT = QWebEngineUrlRequestInfo.ResourceType
    _PINGS = tuple(getattr(_RT, n) for n in ("ResourceTypePing", "ResourceTypeCspReport") if hasattr(_RT, n))

    class Gate(QWebEngineUrlRequestInterceptor):
        """Решает судьбу каждого сетевого запроса страницы. При любой ошибке запрос блокируется."""
        blocked = Signal(str, str)                    

        def __init__(self, parent=None):
            super().__init__(parent)
            self._allow: frozenset = frozenset()

        @property
        def allow(self) -> frozenset:
            return self._allow

        def set_allow(self, allow) -> None:
            self._allow = frozenset(allow)            

        def interceptRequest(self, info):
            try:
                url = info.requestUrl()
                host = url.host()
                d = decide(url.scheme(), host, self._allow, "ping" if info.resourceType() in _PINGS else "other")
                if not d.ok:
                    info.block(True)
                    self.blocked.emit(host or (url.scheme() + ":"), d.reason)
                    return
                info.setHttpHeader(b"DNT", b"1")
                info.setHttpHeader(b"Sec-GPC", b"1")
            except Exception:
                info.block(True)

    class _Popup(QWebEnginePage):
        """Ловит попытку открыть новое окно: само окно не создаётся, адрес уходит на проверку."""
        requested = Signal(QUrl)

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):
            self.requested.emit(url)
            return False

    class SafePage(QWebEnginePage):
        navBlocked = Signal(str, str)                 
        popupRequested = Signal(QUrl)
        fullscreenChanged = Signal(bool)
        allow_fullscreen = False

        def __init__(self, profile, gate: Gate, parent=None):
            super().__init__(profile, parent)
            self._gate = gate
            perm = getattr(self, "permissionRequested", None)          
            if perm is not None:
                perm.connect(lambda p: p.deny())
            else:                                                       
                self.featurePermissionRequested.connect(self._deny_feature)
            cert = getattr(self, "certificateError", None)
            if cert is not None and hasattr(cert, "connect"):
                cert.connect(lambda err: err.rejectCertificate())      
            self.fullScreenRequested.connect(self._fullscreen)

        def _deny_feature(self, origin, feature):
            self.setFeaturePermission(origin, feature, QWebEnginePage.PermissionPolicy.PermissionDeniedByUser)

        def _fullscreen(self, req):
            if self.allow_fullscreen:
                req.accept()
                self.fullscreenChanged.emit(bool(req.toggleOn()))
            else:
                req.reject()

        def acceptNavigationRequest(self, url, nav_type, is_main_frame):
            if is_main_frame:
                d = decide(url.scheme(), url.host(), self._gate.allow)
                if not d.ok:
                    self.navBlocked.emit(url.toString(), d.reason)
                    return False
            return super().acceptNavigationRequest(url, nav_type, is_main_frame)

        def createWindow(self, window_type):
            pop = _Popup(self.profile(), self)
            pop.requested.connect(self.popupRequested)
            return pop

        def javaScriptConsoleMessage(self, level, message, line, source):
            pass                                                        

    def harden(settings, site: Site) -> None:
        A = QWebEngineSettings.WebAttribute
        plan = [(n, False) for n in SETTINGS_OFF] + [(n, True) for n in SETTINGS_ON]
        plan += [("JavascriptEnabled", site.js), ("FullScreenSupportEnabled", site.fullscreen)]
        for name, value in plan:
            attr = getattr(A, name, None)                              
            if attr is not None:
                try:
                    settings.setAttribute(attr, value)
                except Exception:
                    pass

    def make_profile(site: Site, gate: Gate, storage: Optional[Path], parent) -> "QWebEngineProfile":
        if site.persist and storage is not None:
            storage.mkdir(parents=True, exist_ok=True)
            prof = QWebEngineProfile("st-" + site.id, parent)
            prof.setPersistentStoragePath(str(storage / "data"))
            prof.setCachePath(str(storage / "cache"))
            prof.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.AllowPersistentCookies)
            prof.setHttpCacheType(QWebEngineProfile.HttpCacheType.DiskHttpCache)
        else:                                                           
            prof = QWebEngineProfile(parent)
            prof.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.NoPersistentCookies)
            prof.setHttpCacheType(QWebEngineProfile.HttpCacheType.MemoryHttpCache)
        prof.setUrlRequestInterceptor(gate)
        harden(prof.settings(), site)
        return prof


class SiteBrowser(QWidget):
    """Панель просмотра: кнопки навигации, адрес (только чтение), щит, уведомления."""
    closeRequested = Signal()
    allowDomain = Signal(str, str)         
    externalRequested = Signal(str)
    clearRequested = Signal(str)
    fullscreenChanged = Signal(bool)

    def __init__(self):
        super().__init__()
        self.site: Optional[Site] = None
        self._view = self._page = self._profile = self._gate = None
        self._blocked: Dict[str, list] = {}
        self._notice_url = ""
        self._dirty = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.toolbar = QWidget()
        self.toolbar.setFixedHeight(56)
        tl = QHBoxLayout(self.toolbar)
        tl.setContentsMargins(12, 8, 12, 8)
        tl.setSpacing(4)
        self.b_back = icon_button("back", "Назад", 38, 20)
        self.b_fwd = icon_button("forward", "Вперёд", 38, 20)
        self.b_reload = icon_button("reload", "Обновить", 38, 20)
        self.b_home = icon_button("home", "Главная страница сайта", 38, 20)
        hostbox = QFrame()
        hostbox.setObjectName("segbox")
        hl = QHBoxLayout(hostbox)
        hl.setContentsMargins(12, 0, 12, 0)
        hl.setSpacing(8)
        self.lock_icon = QLabel()
        self.lock_icon.setPixmap(icon("lock", C["ok"], 16).pixmap(16, 16))
        self.host_label = QLabel("")
        hl.addWidget(self.lock_icon)
        hl.addWidget(self.host_label, 1)
        hostbox.setFixedHeight(38)
        self.b_shield = QPushButton(" Щит")
        self.b_shield.setObjectName("ghost")
        self.b_shield.setIcon(icon("shield", C["ok"], 18))
        self.b_shield.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_shield.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.b_shield.clicked.connect(self._shield_menu)
        self.b_clear = icon_button("trash", "Очистить данные сайта и открыть заново", 38, 20)
        self.b_ext = icon_button("external", "Открыть во внешнем браузере", 38, 20)
        self.b_close = icon_button("close", "Закрыть сайт", 38, 20)
        for w in (self.b_back, self.b_fwd, self.b_reload, self.b_home):
            tl.addWidget(w)
        tl.addSpacing(6)
        tl.addWidget(hostbox, 1)
        tl.addSpacing(6)
        tl.addWidget(self.b_shield)
        for w in (self.b_clear, self.b_ext, self.b_close):
            tl.addWidget(w)
        root.addWidget(self.toolbar)

        self.notice = QFrame()
        self.notice.setObjectName("card")
        nl = QHBoxLayout(self.notice)
        nl.setContentsMargins(14, 8, 8, 8)
        nl.setSpacing(8)
        self.notice_label = QLabel("")
        self.notice_label.setWordWrap(True)
        self.b_n_allow = QPushButton("Разрешить домен")
        self.b_n_ext = QPushButton("Открыть снаружи")
        self.b_n_close = icon_button("close", "Скрыть", 30, 16)
        for b in (self.b_n_allow, self.b_n_ext):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        nl.addWidget(self.notice_label, 1)
        nl.addWidget(self.b_n_allow)
        nl.addWidget(self.b_n_ext)
        nl.addWidget(self.b_n_close)
        self.notice.hide()
        wrap = QHBoxLayout()
        wrap.setContentsMargins(12, 0, 12, 6)
        wrap.addWidget(self.notice)
        self.notice_wrap = QWidget()
        self.notice_wrap.setLayout(wrap)
        self.notice_wrap.hide()
        root.addWidget(self.notice_wrap)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setTextVisible(False)
        self.progress.hide()
        root.addWidget(self.progress)
        self.holder = QVBoxLayout()
        self.holder.setContentsMargins(0, 0, 0, 0)
        root.addLayout(self.holder, 1)

        self.b_close.clicked.connect(self.closeRequested)
        self.b_clear.clicked.connect(lambda: self.site and self.clearRequested.emit(self.site.id))
        self.b_ext.clicked.connect(self._external_current)
        self.b_n_close.clicked.connect(self._hide_notice)
        self.b_n_ext.clicked.connect(lambda: self.externalRequested.emit(self._notice_url))
        self.b_n_allow.clicked.connect(self._allow_from_notice)
        self.b_back.clicked.connect(lambda: self._view and self._view.back())
        self.b_fwd.clicked.connect(lambda: self._view and self._view.forward())
        self.b_reload.clicked.connect(lambda: self._view and self._view.reload())
        self.b_home.clicked.connect(self._go_home)
        self._shield_timer = QTimer(self)
        self._shield_timer.setSingleShot(True)
        self._shield_timer.setInterval(300)
        self._shield_timer.timeout.connect(self._update_shield)

    def is_open(self) -> bool:
        return self._view is not None

    def open_site(self, site: Site, storage: Optional[Path]) -> None:
        self.close_site()
        self.site = site
        self._blocked.clear()
        self._hide_notice()
        self._update_shield()
        self.host_label.setText(site.host)
        self._gate = Gate(self)
        self._gate.set_allow(site.effective_allow())
        self._gate.blocked.connect(self._on_blocked)
        self._profile = make_profile(site, self._gate, storage, self)
        self._profile.downloadRequested.connect(self._on_download)
        self._page = SafePage(self._profile, self._gate, self)
        self._page.allow_fullscreen = site.fullscreen
        self._page.navBlocked.connect(self._on_nav_blocked)
        self._page.popupRequested.connect(self._on_popup)
        self._page.fullscreenChanged.connect(self._on_fullscreen)
        self._page.urlChanged.connect(lambda u: self.host_label.setText(u.host() or site.host))
        self._page.loadProgress.connect(self._on_progress)
        self._page.renderProcessTerminated.connect(lambda *a: self._show_notice("Страница аварийно закрылась. Нажмите «Обновить»."))
        self._view = QWebEngineView(self)
        self._view.setPage(self._page)
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.holder.addWidget(self._view)
        self._page.load(QUrl(site.url))

    def close_site(self) -> None:
        if self._view is None:
            return
        view, page, prof, gate = self._view, self._page, self._profile, self._gate
        self._view = self._page = self._profile = self._gate = None
        self.site = None
        self.toolbar.show()
        self.progress.hide()
        view.stop()
        self.holder.removeWidget(view)
        view.setParent(None)
        view.deleteLater()
        page.deleteLater()                                       
        QTimer.singleShot(250, prof.deleteLater)
        QTimer.singleShot(300, gate.deleteLater)

    def refresh_allow(self, site: Site) -> None:
        """После «Разрешить домен»: обновляем правила и перезагружаем."""
        if self._gate is None or self.site is None or site.id != self.site.id:
            return
        self.site = site
        self._gate.set_allow(site.effective_allow())
        self._hide_notice()
        target = self._notice_url
        self._notice_url = ""
        if target and decide(QUrl(target).scheme(), QUrl(target).host(), self._gate.allow).ok:
            self._page.load(QUrl(target))
        else:
            self._page.reload()

    def _on_progress(self, p: int) -> None:
        self.progress.setValue(p)
        self.progress.setVisible(0 < p < 100)

    def _on_fullscreen(self, on: bool) -> None:
        self.toolbar.setVisible(not on)
        self.notice_wrap.setVisible(not on and self.notice.isVisible())
        self.fullscreenChanged.emit(on)

    def _on_blocked(self, host: str, reason: str) -> None:
        ent = self._blocked.setdefault(host, [0, reason])
        ent[0] += 1
        self._shield_timer.start()

    def _on_nav_blocked(self, url: str, reason: str) -> None:
        host = QUrl(url).host()
        self._notice_url = url
        hard = reason in HARD_BLOCK
        text = f"Переход на «{host or url}» заблокирован: {REASONS.get(reason, reason)}."
        self._show_notice(text, allow=(not hard and bool(host)), external=(url.startswith("https://") and reason == "not_allowed"))

    def _on_popup(self, url: QUrl) -> None:
        d = decide(url.scheme(), url.host(), self._gate.allow if self._gate else ())
        if d.ok and self._page is not None:
            self._page.load(url)
        else:
            self._on_nav_blocked(url.toString(), d.reason or "not_allowed")

    def _on_download(self, dl) -> None:
        dl.cancel()
        self._show_notice("Загрузка файлов отключена в целях безопасности.")

    def _show_notice(self, text: str, allow: bool = False, external: bool = False) -> None:
        self.notice_label.setText(text)
        self.b_n_allow.setVisible(allow)
        self.b_n_ext.setVisible(external)
        self.notice.show()
        self.notice_wrap.show()

    def _hide_notice(self) -> None:
        self.notice.hide()
        self.notice_wrap.hide()

    def _allow_from_notice(self) -> None:
        host = QUrl(self._notice_url).host()
        if self.site and host:
            self.allowDomain.emit(self.site.id, host)

    def _go_home(self) -> None:
        if self._page is not None and self.site is not None:
            self._page.load(QUrl(self.site.url))

    def _external_current(self) -> None:
        if self._page is not None:
            self.externalRequested.emit(self._page.url().toString())

    def _update_shield(self) -> None:
        total = sum(v[0] for v in self._blocked.values())
        self.b_shield.setText(f" Щит: {total}" if total else " Щит")
        self.b_shield.setToolTip("Заблокированные запросы: нажмите, чтобы посмотреть и разрешить нужные домены" if total
                                 else "Ничего не заблокировано")

    def _shield_menu(self) -> None:
        m = QMenu(self)
        total = sum(v[0] for v in self._blocked.values())
        head = m.addAction(f"Заблокировано запросов: {total}" if total else "Пока ничего не заблокировано")
        head.setEnabled(False)
        if self._blocked:
            m.addSeparator()
        for host, (n, reason) in sorted(self._blocked.items(), key=lambda kv: -kv[1][0])[:12]:
            if reason in HARD_BLOCK or reason == "ping":
                a = m.addAction(f"{host}  ×{n}   ({REASONS.get(reason, reason)})")
                a.setEnabled(False)
            else:
                a = m.addAction(f"Разрешить {host}  ×{n}")
                a.triggered.connect(lambda _=False, h=host: self.site and self.allowDomain.emit(self.site.id, h))
        if self._blocked:
            m.addSeparator()
            m.addAction("Сбросить счётчик").triggered.connect(lambda: (self._blocked.clear(), self._update_shield()))
        m.exec(self.b_shield.mapToGlobal(QPoint(0, self.b_shield.height() + 4)))
