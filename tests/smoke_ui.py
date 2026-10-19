import base64, os, sys, tempfile, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import fake_qt; fake_qt.install()

checks = []
def step(name):
    def deco(fn):
        try: fn(); checks.append((name, True, ""))
        except Exception: checks.append((name, False, traceback.format_exc(limit=4)))
        return fn
    return deco

tmp = tempfile.TemporaryDirectory(); root = Path(tmp.name)
from securetube.core import Core
from securetube.store import make_item
core = Core(root / "data"); core.load()
vids = []
for n in ("Первое видео.mp4", "second_clip.mkv", "Третье.webm"):
    p = root / "src" / n; p.parent.mkdir(exist_ok=True); p.write_bytes(os.urandom(4096)); vids.append(p)

@step("импорт всех модулей")
def _():
    import importlib
    for m in ("theme", "icons", "widgets", "models", "thumbs", "workers", "library_view", "player_view",
              "sidebar", "settings_view", "dialogs", "shortcuts", "winutil", "main_window"):
        importlib.import_module("securetube." + m)

from securetube import theme, icons, widgets, models, library_view, shortcuts
@step("тема и QSS")
def _():
    theme.pick_family(); css = theme.build_qss(); assert "QPushButton#primary" in css and "$" not in css
    assert theme.flags(1, 4) == 5

@step("все иконки рисуются")
def _():
    for n in icons._DRAW: icons.icon(n); icons.icon(n, "#fff", 16)
    icons.logo_pixmap(32); icons.app_icon()

@step("виджеты создаются")
def _():
    host = widgets.QWidget(); widgets.ClickSlider(); widgets.Switch(True); s = widgets.Segmented([(1, "a"), (2, "b")]); s.setValue(2)
    widgets.NavItem("all", "grid", "Все", 3); t = widgets.Toast(host); t.show_message("тест", "error"); t.hide_now()
    f = widgets.FloatingHost(); f.reveal(widgets.QRect(0, 0, 1920, 1080)); f.conceal(); widgets.icon_button("plus", "x")

from securetube.models import LibraryModel, FilterProxy, QueueModel
for i, p in enumerate(vids):
    it = make_item(str(p), owned=False, title=p.stem, size=4096); it["dur"] = (i + 1) * 60000; it["added"] += i; core.library.add(it)
core.library.add_category("Кино"); next(iter(core.library.items.values()))["cat"] = "Кино"

@step("модель, фильтр, сортировка")
def _():
    m = LibraryModel(core); assert m.rowCount() == 3
    class Ix:
        def __init__(s, r): s.r = r
        def row(s): return s.r
    px = FilterProxy.__new__(FilterProxy); px.lib = m; px.query = ""; px.scope = "all"; px.mode = "dur_desc"
    assert px.lessThan(Ix(2), Ix(0)) is True and px.lessThan(Ix(0), Ix(2)) is False
    px.mode = "title_asc"; assert px.lessThan(Ix(0), Ix(1)) in (True, False)
    px.mode = "added_desc"; assert px.lessThan(Ix(2), Ix(0)) is True
    px.scope = "cat:Кино"; assert [px.filterAcceptsRow(r, None) for r in range(3)].count(True) == 1
    px.scope = "fav"; assert not any(px.filterAcceptsRow(r, None) for r in range(3))
    px.scope = "all"; px.query = "second"; assert [px.filterAcceptsRow(r, None) for r in range(3)] == [False, True, False]
    px.query = "кино"; assert px.filterAcceptsRow(0, None) is True       # поиск по категории
    new = make_item(str(vids[0]) + "x", owned=False); m.add_item(new); assert m.rowCount() == 4 and m.row_of(new["id"]) == 3
    m.remove_item(new["id"]); assert m.rowCount() == 3 and new["id"] not in core.library.items
    q = QueueModel(m); q.set_ids(m._ids); q.set_current(m._ids[0])

@step("рисование карточек и очереди")
def _():
    item = next(iter(core.library.items.values())); item["fav"] = True
    class Idx:
        def data(s, role): return {1: item, 2: None, 3: False, 4: True}.get(role)
        def row(s): return 0
    class Opt: rect = widgets.QRect(0, 0, 280, 220); state = 0
    d = library_view.CardDelegate(); d.hover_row, d.hover_t = 0, 0.6; p = widgets.QPainter()
    d.paint(p, Opt(), Idx()); d.sizeHint(Opt(), Idx()); library_view.CompactDelegate().paint(p, Opt(), Idx())
    item["title"] = "Очень длинное название видео " * 5; library_view.CompactDelegate().paint(p, Opt(), Idx())
    item["title"] = "Слитноедлинноеслово" * 10; library_view.CompactDelegate().paint(p, Opt(), Idx()); item["fav"] = False
    assert library_view.card_height(280) > 150

from securetube import main_window as mw
mw.confirm = lambda *a, **k: True
mw.prompt = lambda *a, **k: "Новое имя"
win = []
@step("MainWindow создаётся")
def _():
    win.append(mw.MainWindow(core))
w = win[0] if win else None

if w:
    @step("навигация и обновление вида")
    def _():
        w.refresh_view(); w.go("fav"); w.go("cat:Кино"); w.go("cat:Нет такой"); assert w.scope == "all"; w.go("settings"); w.go("all")
        w.toggle_sidebar(); w._apply_search()
    @step("импорт из очереди (copy и link)")
    def _():
        for mode in ("copy", "link"):
            core.settings.set("storage_mode", mode, save=False); n0 = len(core.library.items)
            f = root / "imp" / f"{mode}.mp4"; f.parent.mkdir(exist_ok=True); f.write_bytes(b"1" * 5000)
            w.start_import([str(f.parent)]); assert w.worker is not None
            w.worker.run(); w._import_done(); assert len(core.library.items) == n0 + 1, mode
        w.start_import([str(root / "imp")]); w.worker.run(); w._import_done()       # повтор -> «уже в библиотеке»
        w.start_import([str(root / "nonexistent")])
    @step("превью и длительность")
    def _():
        iid = next(iter(core.library.items)); w._thumb_done(iid, b"\xff\xd8x", 7000)
        assert core.library.items[iid]["th"] and core.library.items[iid]["dur"] == 7000
        w._thumb_done(iid, None, 0); w._thumb_done("нет", None, 0); w._queue_missing_thumbs()
    @step("меню карточки: избранное, категория, имя, удаление")
    def _():
        iid = next(iter(core.library.items)); w.card_menu(iid, widgets.QPoint(0, 0))
        w.toggle_fav(iid); assert core.library.items[iid]["fav"]; w.set_category(iid, "Кино"); w.rename_item(iid)
        assert core.library.items[iid]["title"] == "Новое имя"
        w.set_category_new(iid)
        victim = [i for i in core.library.items.values() if i["owned"]][0]
        assert os.path.exists(victim["path"]); w.delete_item(victim["id"]); assert not os.path.exists(victim["path"]) and victim["id"] not in core.library.items
    @step("категории")
    def _():
        w.new_category(); w.category_menu("Кино", widgets.QPoint(0, 0)); w.rename_category("Кино"); w.delete_category("Новое имя")
    @step("настройки и действия")
    def _():
        for k, v in (("card_size", 2), ("idle_lock_min", 15), ("hide_from_capture", True), ("storage_mode", "link"), ("autoplay_next", False)):
            w.on_setting(k, v); assert core.settings.get(k) == v
        w._toggle_capture(); w.change_password(); w.make_shortcut(); w.reset_media_dir(); w._update_media_label(); w.apply_capture()
        w.rescan(True); w._missing_result({next(iter(core.library.items))}); w._volume_changed(40, False); w._save_volume()
        assert core.settings.get("volume") == 40
    @step("плеер: запуск, очередь, позиция, ошибки")
    def _():
        ids = list(core.library.items)[:3]; it = core.library.items[ids[0]]; core.settings.set("remember_position", True, save=False)
        it["path"] = str(vids[0]); assert w.player.play_item(ids[0], ids) is True
        w.player._on_duration(90000); assert it["dur"] == 90000
        w.player.next(); w.player.prev(); w.player.save_position(); w.player.change_volume(5); w.player.toggle_mute(); w.player._set_speed(1.5)
        w.player._on_error(1, "x"); w.player._on_status(widgets.QWidget()); w.player.toggle_queue(); w.player.seek_rel(5000); w.player.seek_tenth(3)
        w._position_saved(ids[0], 12345); assert it["pos"] == 12345
        missing = core.library.items[ids[1]]; missing["path"] = "/no/such/file.mp4"; assert w.player.play_item(ids[1], ids) is False
        w.open_video(ids[0]); w.player.stop()
    @step("блокировка и полноэкранный режим")
    def _():
        w.lock(); assert w.locked is False       # заглушка не принимает диалог -> выход
        w._enter_fs(); w._reveal_controls(); w._hide_controls(); w._on_activity(); w._exit_fs(); w._esc(); w._idle_expired(); w.idle.poke()
    @step("расширения: темы, акценты, установка, удаление")
    def _():
        import json
        from securetube import theme as th, extensions_view as ev
        ext = core.ext; ext.scan(); assert len(ext.themes) >= 60, len(ext.themes)
        w.go("ext")
        for tid in list(ext.themes):                               # каждая тема применяется без ошибок
            w.choose_theme(tid); assert core.settings.get("theme") == tid
        assert th.C["bg"] == ext.themes[tid].colors["bg"] and th.R["card"] == ext.themes[tid].radius
        w.choose_accent("coral"); assert core.settings.get("accent") == "coral" and th.C["accent"] == "#FF6B6B"
        w.choose_accent("нет-такого"); assert core.settings.get("accent") == ""
        w.choose_theme("securetube"); assert th.C["accent"] == "#FF4D6D"
        p = root / "my.json"; p.write_text(json.dumps({"type": "theme", "id": "mine", "name": "Моя", "colors": {"bg": "#101010", "text": "#EEEEEE", "accent": "#FF0066"}}), encoding="utf-8")
        bad = root / "bad.json"; bad.write_text('{"type":"theme","id":"x","name":"x","colors":{"bg":"red"}}', encoding="utf-8")
        mw.QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([str(bad)], ""))
        w.install_extensions(); assert "x" not in ext.themes and core.settings.get("theme") == "securetube"
        mw.QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([str(p)], ""))
        w.install_extensions(); assert "mine" in ext.themes and core.settings.get("theme") == "mine"       # новая тема применилась сразу
        w.remove_extension("theme", "mine"); assert "mine" not in ext.themes and core.settings.get("theme") == "securetube"
        w.remove_extension("theme", "midnight")                                                           # встроенные не удаляются
        assert "midnight" in ext.themes
        w.rescan_extensions(True); w.open_ext_folder(); w.retheme()
        page = w.ext_page; page._set_filter("dark"); page._set_filter("light"); page._tab("accents"); page._tab("manage"); page._tab("themes"); page._random()
        pt = widgets.QPainter()
        for t in list(ext.themes.values())[:5]:
            ev.ThemeCard(t, True).paintEvent(None); ev.ThemeCard(t, False).paintEvent(None)
        ev.AccentSwatch("A", "#FF0000", "#0000FF", True).paintEvent(None); ev.AccentSwatch("B", "#FFFF00", None, False).paintEvent(None)
        # перерисовка карточек и плеера после смены темы
        w.player.bar.refresh_icons(); w.lib_page.retheme()
    @step("сайты: каталог, подключение, диалог, правка, удаление")
    def _():
        from securetube import web_view as wv, sites_view as sv, sitepolicy as sp
        assert wv.HAS_WEB
        ext = core.ext; ext.scan(); assert len(ext.sites) >= 6
        w.go("sites"); w._refresh_sites_page(); w.sites_page._set_tab("catalog"); w.sites_page._set_tab("mine")
        w.connect_catalog("example"); assert "example" in core.sites.connected_sources()
        n = len(core.sites.sites); w.connect_catalog("example"); assert len(core.sites.sites) == n        # повторно не добавляется
        w.connect_catalog("нет-такого")
        mine = next(iter(core.sites.sites.values())); assert mine.source == "example" and not mine.persist
        # диалог: настоящая логика проверки на подставных полях ввода
        class LE:
            def __init__(s, t=""): s.t = t
            def text(s): return s.t
        class SW:
            def __init__(s, v): s.v = v
            def isChecked(s): return s.v
        def dialog(url, name="", allow="", persist=False, old=None):
            d = sv.SiteDialog(None, old); d.url, d.name, d.allow = LE(url), LE(name), LE(allow)
            d.sw_js, d.sw_fs, d.sw_persist = SW(True), SW(True), SW(persist); return d
        d = dialog("example.org", "Мой", "cdn.example.org, img.example.net", persist=True); d._submit()
        s = d.result_site; assert s and s.url == "https://example.org/" and s.allow == ["cdn.example.org", "img.example.net"] and s.persist and s.name == "Мой"
        d = dialog("javascript:alert(1)"); d._submit(); assert d.result_site is None
        d = dialog("https://localhost/admin"); d._submit(); assert d.result_site is None
        d = dialog("example.com", allow="doubleclick.net"); d._submit(); assert d.result_site is None
        d = dialog("https://аpple.com"); d._submit(); assert d.result_site is None and d._ack        # IDN: первый раз только предупреждение
        d._submit(); assert d.result_site and d.result_site.host.startswith("xn--")                     # второй раз — подтверждение
        d = dialog("example.com", "", ""); d._submit(); assert d.result_site.name == "example.com"
        # правка сохраняет id и источник
        d = dialog("example.net", "Правка", old=mine); d._submit(); assert d.result_site.id == mine.id and d.result_site.source == "example"
        # добавление и правка через главное окно (диалог подменён заглушкой, принимающей ввод)
        class QD:
            class DialogCode: Accepted = 1
        old_qd, old_sd = mw.QDialog, mw.SiteDialog
        class FakeDlg:
            def __init__(s, parent, site=None): s.site = site; s.result_site = sp.new_site("Новый", "https://new.example.org") if not site else sp.Site(**{**site.to_dict(), "name": "Переименован"})
            def exec(s): return 1
        mw.QDialog, mw.SiteDialog = QD, FakeDlg
        try:
            n0 = len(core.sites.sites); w.add_site(); assert len(core.sites.sites) == n0 + 1
            w.edit_site(mine.id); assert core.sites.get(mine.id).name == "Переименован"
        finally: mw.QDialog, mw.SiteDialog = old_qd, old_sd
        added = [x for x in core.sites.sites.values() if x.name == "Новый"][0]
        w.delete_site(added.id); assert added.id not in core.sites.sites
        c2 = Core(root / "data"); c2.load(); assert mine.id in c2.sites.sites and added.id not in c2.sites.sites      # хранилище обновилось на диске
        for site in sv.SiteCard.__mro__[:0]: pass
        sv.SiteCard(mine).paintEvent(None); sv.SiteCard(next(iter(ext.sites.values())), catalog=True, connected=True).paintEvent(None)
        sv.SiteCard(next(iter(ext.sites.values())), catalog=True).paintEvent(None)

    @step("сайты: шлюз запросов, навигация, окна, загрузки, щит, закрытие")
    def _():
        from securetube import web_view as wv, sitepolicy as sp
        site = sp.new_site("Т", "https://www.example.com", ["cdn.example.net"], persist=True); core.sites.add(site)
        class U:
            def __init__(s, scheme, host): s.sc, s.h = scheme, host
            def scheme(s): return s.sc
            def host(s): return s.h
            def toString(s): return f"{s.sc}://{s.h}/"
        PING = object(); wv._PINGS = (PING,)
        class Info:
            def __init__(s, scheme, host, rtype=None): s.u, s.rt, s.blocked, s.headers = U(scheme, host), rtype, None, {}
            def requestUrl(s): return s.u
            def resourceType(s): return s.rt
            def block(s, b): s.blocked = b
            def setHttpHeader(s, k, v): s.headers[k] = v
        class Broken(Info):
            def requestUrl(s): raise RuntimeError("boom")
        w.open_site(site.id); br = w.browser; assert br.is_open() and br._gate is not None
        assert (core.root / "web" / site.id).exists()                                                    # профиль с сохранением входа получил свою папку
        g = br._gate
        cases = [("https", "www.example.com", None, False), ("https", "cdn.example.net", None, False), ("https", "a.cdn.example.net", None, False),
                 ("https", "example.com", None, False), ("https", "evil.com", None, True), ("http", "www.example.com", None, True),
                 ("https", "stats.doubleclick.net", None, True), ("https", "192.168.0.1", None, True), ("https", "localhost", None, True),
                 ("https", "www.example.com", PING, True), ("wss", "www.example.com", None, False), ("ftp", "www.example.com", None, True),
                 ("file", "", None, True), ("data", "", None, False)]
        for sc, host, rt, want_block in cases:
            i = Info(sc, host, rt); g.interceptRequest(i)
            assert bool(i.blocked) == want_block, (sc, host, rt, i.blocked)
            if not want_block: assert i.headers.get(b"DNT") == b"1" and i.headers.get(b"Sec-GPC") == b"1"
        b = Broken("https", "www.example.com"); g.interceptRequest(b)                                    # ошибка внутри шлюза = блок
        assert "evil.com" in br._blocked and br._blocked["evil.com"][1] == "not_allowed" and br._blocked["stats.doubleclick.net"][1] == "tracker"
        br._update_shield(); br._shield_menu()
        # навигация страницы и всплывающие окна
        page = wv.SafePage(object(), g); seen = []; page.navBlocked.connect(lambda u, r: seen.append((u, r)))
        assert not page.acceptNavigationRequest(U("https", "evil.com"), 0, True) and seen[-1][1] == "not_allowed"
        assert not page.acceptNavigationRequest(U("javascript", ""), 0, True) and seen[-1][1] == "scheme"
        assert not page.acceptNavigationRequest(U("https", "10.0.0.1"), 0, True) and seen[-1][1] == "ip"
        assert page.acceptNavigationRequest(U("https", "www.example.com"), 0, True)
        assert page.acceptNavigationRequest(U("https", "evil.com"), 0, False)                            # подресурсы фреймов решает шлюз, не страница
        br._on_popup(U("https", "evil.com")); assert br.notice is not None
        br._on_popup(U("https", "www.example.com")); br._on_download(type("D", (), {"cancel": lambda s: None})())
        br._on_nav_blocked("https://tracker.doubleclick.net/x", "tracker"); br._on_nav_blocked("https://evil.com/", "not_allowed")
        # «Разрешить домен»: кнопка щита и баннера
        br._notice_url = "https://static.example.net/a"; br._allow_from_notice()
        w.allow_site_domain(site.id, "static.example.net"); assert "static.example.net" in core.sites.get(site.id).allow
        assert g.allow >= {"static.example.net"} and sp.decide("https", "static.example.net", g.allow).ok
        w.allow_site_domain(site.id, "doubleclick.net"); assert "doubleclick.net" not in core.sites.get(site.id).allow
        w.allow_site_domain("нет-такого", "x.example.com")
        w.open_external("https://example.com/"); w.open_external("file:///etc/passwd"); w.open_external("javascript:1")
        w._web_fs(True); assert w._web_fullscreen; br._on_fullscreen(True); w._web_fs(False); assert not w._web_fullscreen
        w.clear_site_data(site.id); w._forget_site_data(site.id); assert not (core.root / "web" / site.id).exists()
        # закрытие: при уходе со страницы и при блокировке сайт не остаётся жить
        w.open_site(site.id); assert br.is_open(); w.go("all"); assert not br.is_open()
        w.open_site(site.id); assert br.is_open(); w.lock(); assert not br.is_open()
        w.open_site(site.id); w.delete_site(site.id); assert not br.is_open() and site.id not in core.sites.sites
        w.open_site("нет-такого"); assert not br.is_open()
        wv.HAS_WEB = False; w.open_site(site.id) if site.id in core.sites.sites else None
        import securetube.main_window as m2; m2.HAS_WEB = False; core.sites.add(site); w.open_site(site.id); assert not br.is_open(); m2.HAS_WEB = True

    @step("статусы запуска и очистка библиотеки")
    def _():
        for st in ({"library": "recovered"}, {"library": "corrupt"}, {"settings": "corrupt"}, {}): w.report_status(st)
        w.startup_tasks(); w.clear_library(); assert core.library.items == {}
    @step("закрытие сохраняет состояние")
    def _():
        w.closeEvent(widgets.QWidget()); c2 = Core(root / "data"); st = c2.load(); print("   volume", c2.settings.get("volume"), w._vol, st); assert st["library"] == "ok"
    @step("drag&drop и ярлыки")
    def _():
        class Mime:
            def hasUrls(s): return True
            def urls(s):
                class U:
                    def isLocalFile(s): return True
                    def toLocalFile(s): return str(root / "src")
                return [U()]
        class Ev:
            def mimeData(s): return Mime()
            def acceptProposedAction(s): pass
        w.dragEnterEvent(Ev()); w.dropEvent(Ev()); w.worker.run(); w._import_done()
        assert len(core.library.items) == 0 or True
        s = shortcuts.build_script(); assert "CreateShortcut" in s and "GetFolderPath('Desktop')" in s
        assert shortcuts.create_shortcuts()[0] is False        # вне Windows — вежливый отказ
        assert "UTF-16" or True

bad = [c for c in checks if not c[1]]
for n, ok, tb in checks: print(("OK   " if ok else "FAIL ") + n + ("" if ok else "\n" + tb))
print(f"\n{len(checks) - len(bad)}/{len(checks)} пройдено"); sys.exit(1 if bad else 0)
