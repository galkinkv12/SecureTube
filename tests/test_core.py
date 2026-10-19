import json, os, sys, tempfile, time, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from securetube import util, importer
from securetube.core import Core, KeyUnavailable
from securetube.vault import Vault, VaultError
from securetube.keystore import KeyStore
from securetube.store import make_item, Library, SecureFile
from securetube import auth as authmod


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "data"
    def tearDown(self):
        self.tmp.cleanup()

    # ---------- vault
    def test_vault_roundtrip_and_tamper(self):
        v = Vault(os.urandom(32))
        blob = v.seal(b"secret", "lib")
        self.assertEqual(v.open(blob, "lib"), b"secret")
        self.assertNotIn(b"secret", blob)
        with self.assertRaises(VaultError): v.open(blob, "cfg")          # другой label
        bad = bytearray(blob); bad[-1] ^= 1
        with self.assertRaises(VaultError): v.open(bytes(bad), "lib")   # правка
        with self.assertRaises(VaultError): Vault(os.urandom(32)).open(blob, "lib")  # другой ключ
        with self.assertRaises(VaultError): v.open(b"junk", "lib")

    # ---------- keystore
    def test_keystore_persist_and_subkeys(self):
        self.root.mkdir()
        k1 = KeyStore(self.root / "k"); key = k1.load()
        self.assertTrue(k1.created); self.assertEqual(len(key), 32)
        k2 = KeyStore(self.root / "k")
        self.assertEqual(k2.load(), key); self.assertFalse(k2.created)
        self.assertNotEqual(k2.subkey("a"), k2.subkey("b"))
    def test_keystore_corrupt(self):
        self.root.mkdir(); (self.root / "k").write_bytes(b"garbage!")
        with self.assertRaises(KeyUnavailable): KeyStore(self.root / "k").load()
    def test_keystore_foreign_dpapi(self):
        self.root.mkdir(); (self.root / "k").write_bytes(b"XK1\x01" + b"x" * 40)
        if os.name != "nt":
            with self.assertRaises(KeyUnavailable): KeyStore(self.root / "k").load()

    # ---------- core / persistence
    def test_core_persistence_encrypted_on_disk(self):
        c = Core(self.root); c.load()
        it = make_item("/videos/Секретное видео.mp4", owned=False, title="Секретное видео", size=10)
        c.library.add(it); c.library.add_category("Тайная категория"); c.library.save()
        c.settings.set("volume", 33)
        raw = (c.core_dir / "lib.xt").read_bytes() + (c.core_dir / "cfg.xt").read_bytes()
        for needle in ("Секретное".encode(), b"videos", "Тайная".encode(), b"volume"):
            self.assertNotIn(needle, raw)
        c2 = Core(self.root); st = c2.load()
        self.assertEqual(st["library"], "ok")
        self.assertEqual(c2.library.items[it["id"]]["title"], "Секретное видео")
        self.assertEqual(c2.library.categories, ["Тайная категория"])
        self.assertEqual(c2.settings.get("volume"), 33)
    def test_tamper_falls_back_to_backup(self):
        c = Core(self.root); c.load()
        a = make_item("/a.mp4", owned=False); c.library.add(a); c.library.save()
        b = make_item("/b.mp4", owned=False); c.library.add(b); c.library.save()  # создаёт .bak с A
        p = c.core_dir / "lib.xt"; data = bytearray(p.read_bytes()); data[20] ^= 0xFF; p.write_bytes(bytes(data))
        c2 = Core(self.root); st = c2.load()
        self.assertEqual(st["library"], "recovered")
        self.assertIn(a["id"], c2.library.items)
        self.assertTrue(any(f.name.startswith("lib.xt.bad-") for f in c2.core_dir.iterdir()))
    def test_total_corruption_does_not_crash(self):
        c = Core(self.root); c.load(); c.library.add(make_item("/a.mp4", owned=False)); c.library.save()
        for f in c.core_dir.glob("lib.xt*"): f.write_bytes(b"x" * 80)
        c2 = Core(self.root); self.assertEqual(c2.load()["library"], "corrupt")
        self.assertEqual(c2.library.items, {})
        c2.library.save()                       # дальше работаем с чистого листа
        self.assertEqual(Core(self.root).load()["library"], "ok")
    def test_settings_validation(self):
        c = Core(self.root); c.load()
        c.settings.set("volume", 999); self.assertEqual(c.settings.get("volume"), 100)
        c.settings.set("storage_mode", "rm -rf"); self.assertEqual(c.settings.get("storage_mode"), "copy")
        c.settings.set("idle_lock_min", True); self.assertEqual(c.settings.get("idle_lock_min"), 5)
        c.settings.set("autoplay_next", "yes"); self.assertEqual(c.settings.get("autoplay_next"), True)
    def test_item_normalization_drops_garbage(self):
        c = Core(self.root); c.load()
        blob = json.dumps({"items": [{"id": "x", "path": "/ok.mp4", "dur": "bad", "fav": 1}, {"path": ""}, 5], "cats": ["A", "A", "", 3]})
        c.library.file.write(blob.encode()); c2 = Core(self.root); c2.load()
        self.assertEqual(list(c2.library.items), ["x"]); self.assertEqual(c2.library.items["x"]["dur"], 0)
        self.assertIs(c2.library.items["x"]["fav"], False); self.assertEqual(c2.library.categories, ["A"])
    def test_thumbs_encrypted(self):
        c = Core(self.root); c.load()
        c.thumbs.save("abc", b"\xff\xd8JPEGDATA")
        self.assertNotIn(b"JPEGDATA", (c.cache_dir / "abc.xt").read_bytes())
        self.assertEqual(c.thumbs.load("abc"), b"\xff\xd8JPEGDATA"); self.assertIsNone(c.thumbs.load("nope"))
        os.rename(c.cache_dir / "abc.xt", c.cache_dir / "zzz.xt")
        self.assertIsNone(c.thumbs.load("zzz"))        # файл нельзя подсунуть под другим id
    def test_categories(self):
        c = Core(self.root); c.load(); L = c.library
        self.assertEqual(L.add_category("  Кино  "), "Кино"); self.assertIsNone(L.add_category("кино"))
        it = make_item("/a.mp4", owned=False); it["cat"] = "Кино"; L.add(it)
        self.assertEqual(L.rename_category("Кино", "Фильмы"), "Фильмы"); self.assertEqual(it["cat"], "Фильмы")
        L.delete_category("Фильмы"); self.assertEqual(it["cat"], ""); self.assertEqual(L.categories, [])
    def test_adopt_orphans(self):
        c = Core(self.root); c.load(); m = c.media_dir()
        (m / "a1b2c3.mp4").write_bytes(b"v"); (m / "notes.txt").write_text("x")
        got = c.library.adopt_orphans(m); self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["id"], "a1b2c3"); self.assertEqual(c.library.adopt_orphans(m), [])

    # ---------- auth
    def test_auth_flow(self):
        k = os.urandom(32); self.root.mkdir()
        a = authmod.Auth(self.root, k, first_run=True)
        self.assertEqual(a.ban_remaining(), 0)
        self.assertEqual(a.attempt("nope"), ("wrong", 2)); self.assertEqual(a.attempt("nope"), ("wrong", 1))
        res, left = a.attempt("nope"); self.assertEqual(res, "banned"); self.assertGreater(left, 86000)
        self.assertEqual(authmod.Auth(self.root, k, False).attempt("anything")[0], "banned")   # перезапуск не снимает
        self.assertGreater(authmod.Auth(self.root, k, False).ban_remaining(), 0)
    def test_auth_tamper_and_delete_cause_ban(self):
        k = os.urandom(32); self.root.mkdir(); a = authmod.Auth(self.root, k, True)
        f = self.root / "st.dat"; d = json.loads(f.read_text()); d["fails"] = 0; d["ban_until"] = 0; d["hash"] = "00" * 32
        f.write_text(json.dumps(d))
        self.assertGreater(authmod.Auth(self.root, k, False).ban_remaining(), 0)
        f.unlink(); self.assertGreater(authmod.Auth(self.root, k, False).ban_remaining(), 0)
    def test_auth_clock_rollback(self):
        k = os.urandom(32); self.root.mkdir(); a = authmod.Auth(self.root, k, True)
        for _ in range(3): a.attempt("x")
        real = time.time; time.time = lambda: real() - 7 * 86400
        try: self.assertGreater(authmod.Auth(self.root, k, False).ban_remaining(), 80000)
        finally: time.time = real
    def test_auth_change_password(self):
        k = os.urandom(32); self.root.mkdir(); a = authmod.Auth(self.root, k, True)
        # подменим стартовый хэш известным паролем
        s = a._load(); import secrets as sc; salt = sc.token_bytes(16)
        s["salt"], s["hash"] = salt.hex(), authmod._derive("oldpassword", salt).hex(); a._save(s)
        self.assertEqual(a.set_password("oldpassword", "short"), "short")
        self.assertEqual(a.set_password("wrong", "newpassword1"), "wrong")
        self.assertEqual(a.set_password("oldpassword", "newpassword1"), "ok")
        self.assertEqual(a.attempt("oldpassword")[0], "wrong"); self.assertEqual(a.attempt("newpassword1")[0], "ok")

    # ---------- import
    def _vid(self, name, data=b"0" * 5000):
        p = Path(self.tmp.name) / "src" / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data); return p
    def test_import_copy_link_dupes_and_delete(self):
        c = Core(self.root); c.load(); media = c.media_dir()
        src = self._vid("Мой_фильм.2024.mp4"); prog = []
        it = importer.import_one(src, c.library.orig_set(), "copy", media, False, prog.append, lambda: False)
        c.library.add(it)
        self.assertTrue(Path(it["path"]).exists()); self.assertTrue(it["owned"]); self.assertEqual(it["title"], "Мой фильм 2024")
        self.assertEqual(Path(it["path"]).read_bytes(), src.read_bytes()); self.assertEqual(prog[-1], 1.0)
        self.assertIsNone(importer.import_one(src, c.library.orig_set(), "copy", media, False, prog.append, lambda: False))  # дубль
        src2 = self._vid("b.mkv"); it2 = importer.import_one(src2, c.library.orig_set(), "link", media, False, lambda f: None, lambda: False)
        self.assertFalse(it2["owned"]); self.assertEqual(it2["path"], str(src2))
        src3 = self._vid("c.webm"); it3 = importer.import_one(src3, c.library.orig_set(), "copy", media, True, lambda f: None, lambda: False)
        self.assertFalse(src3.exists()); self.assertTrue(Path(it3["path"]).exists())
    def test_import_errors(self):
        c = Core(self.root); c.load()
        with self.assertRaises(importer.ImportFailed): importer.import_one(Path("/no/such.mp4"), c.library.orig_set(), "copy", c.media_dir(), False, lambda f: None, lambda: False)
        with self.assertRaises(importer.ImportFailed): importer.import_one(self._vid("e.mp4", b""), c.library.orig_set(), "copy", c.media_dir(), False, lambda f: None, lambda: False)
    def test_import_cancel_leaves_no_partial(self):
        c = Core(self.root); c.load(); media = c.media_dir(); big = self._vid("big.mp4", b"1" * (9 * 1024 * 1024))
        n = {"i": 0}
        def cancel(): n["i"] += 1; return n["i"] > 1
        with self.assertRaises(importer.Cancelled): importer.import_one(big, c.library.orig_set(), "copy", media, False, lambda f: None, cancel)
        self.assertEqual([p for p in media.iterdir()], [])
    def test_import_no_disk_space(self):
        c = Core(self.root); c.load(); src = self._vid("x.mp4")
        old = importer.MIN_FREE; importer.MIN_FREE = 10 ** 18
        try:
            with self.assertRaises(importer.ImportFailed) as cm: importer.import_one(src, c.library.orig_set(), "copy", c.media_dir(), False, lambda f: None, lambda: False)
            self.assertIn("места", str(cm.exception)); self.assertEqual(list(c.media_dir().iterdir()), [])
        finally: importer.MIN_FREE = old

    # ---------- util
    def test_scan(self):
        a = self._vid("z10.mp4"); self._vid("z2.mkv"); self._vid("notes.txt"); self._vid(".hidden.mp4"); self._vid("sub/deep.MOV")
        got = [p.name for p in util.scan([a.parent, a])]
        self.assertEqual(sorted(got), ["deep.MOV", "z10.mp4", "z2.mkv"])
        self.assertEqual(len(got), 3)                         # дубль z10.mp4 не задвоился
        self.assertLess(got.index("z2.mkv"), got.index("z10.mp4"))   # натуральная сортировка
    def test_formatters(self):
        self.assertEqual(util.fmt_ms(65000), "1:05"); self.assertEqual(util.fmt_ms(3725000), "1:02:05"); self.assertEqual(util.fmt_ms(-5), "0:00")
        self.assertEqual(util.fmt_size(1536), "1.5 КБ"); self.assertEqual(util.fmt_size(10), "10 Б")
        self.assertEqual(util.plural(1, ("день", "дня", "дней")), "день"); self.assertEqual(util.plural(3, ("день", "дня", "дней")), "дня")
        self.assertEqual(util.plural(11, ("день", "дня", "дней")), "дней"); self.assertEqual(util.plural(22, ("день", "дня", "дней")), "дня")
        now = time.time(); self.assertEqual(util.fmt_added(now), "сегодня"); self.assertEqual(util.fmt_added(now - 86400 * 3, now), "3 дня назад")
        self.assertEqual(util.clean_title("My_great.video-01.mp4"), "My great video-01"); self.assertEqual(util.fmt_total(3 * 3600000 + 12 * 60000), "3 ч 12 мин")


class Migration(unittest.TestCase):
    """Переименование XXXtube -> SecureTube не должно терять данные пользователя."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.base = Path(self.tmp.name)
        self.old_env = {k: os.environ.get(k) for k in ("XDG_DATA_HOME", "SECURETUBE_HOME", "LOCALAPPDATA")}
        os.environ["XDG_DATA_HOME"] = str(self.base); os.environ["LOCALAPPDATA"] = str(self.base); os.environ.pop("SECURETUBE_HOME", None)
        from securetube import paths; self.paths = paths
        self.new = self.base / ("SecureTube" if os.name == "nt" else "securetube")
        self.old = self.base / self.paths.LEGACY_NAMES[0]
    def tearDown(self):
        for k, v in self.old_env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        self.tmp.cleanup()
    def test_data_survives_rename(self):
        c = Core(self.old); c.load(); it = make_item("/v/a.mp4", owned=False, title="Моё видео"); c.library.add(it); c.library.save()
        c.settings.set("volume", 41); (c.media_dir() / "x.mp4").write_bytes(b"v")
        root = self.paths.data_root()
        self.assertEqual(root, self.new); self.assertFalse(self.old.exists())
        c2 = Core(root); st = c2.load()
        self.assertEqual((st["settings"], st["library"]), ("ok", "ok"))              # тот же ключ открывает те же файлы
        self.assertEqual(c2.library.items[it["id"]]["title"], "Моё видео"); self.assertEqual(c2.settings.get("volume"), 41)
        self.assertTrue((c2.media_dir() / "x.mp4").exists())
    def test_pre_rename_password_state_kept(self):
        c = Core(self.old); c.load()
        for _ in range(3): c.auth.attempt("wrong-password")                    # бан, выставленный до обновления, не сбрасывается переименованием
        c2 = Core(self.paths.data_root()); self.assertGreater(c2.auth.ban_remaining(), 80000)
    def test_new_folder_wins_and_legacy_untouched(self):
        self.old.mkdir(); (self.old / "marker").write_text("old"); self.new.mkdir()
        self.assertEqual(self.paths.data_root(), self.new); self.assertTrue((self.old / "marker").exists())
    def test_fresh_install_has_no_legacy(self):
        self.assertEqual(self.paths.data_root(), self.new); self.assertTrue(self.new.is_dir())
    def test_key_derivation_constants_unchanged(self):
        import securetube.keystore as ks
        self.assertEqual(ks._ENTROPY, b"XXXtube/keywrap/v1")                    # менять нельзя: ключи прежних версий
        k = ks.KeyStore(self.base / "k"); k.load(); import hmac, hashlib
        self.assertEqual(k.subkey("vault"), hmac.new(k.load(), b"xxxtube/vault", hashlib.sha256).digest())


if __name__ == "__main__":
    unittest.main(verbosity=1)
