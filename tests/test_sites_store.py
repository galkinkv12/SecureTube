import json, os, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from securetube import extensions as ex, sitepolicy as sp
from securetube.core import Core

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = {"type": "site", "id": "demo", "name": "Демо", "url": "https://example.com", "allow": ["example.com"], "permissions": {"js": True}}


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()

    def test_persisted_encrypted_and_reloaded(self):
        c = Core(self.root / "d"); c.load(); s = sp.new_site("Мой приватный сайт", "https://secret-place.example.org/path", ["cdn.secret-place.example.org"], persist=True)
        c.sites.add(s); c.sites.save()
        blob = (c.core_dir / "sites.xt").read_bytes()
        for needle in ("secret-place".encode(), "приватный".encode(), b"example.org"): self.assertNotIn(needle, blob)
        c2 = Core(self.root / "d"); st = c2.load(); got = c2.sites.get(s.id)
        self.assertEqual(st["sites"], "ok"); self.assertEqual(got, s); self.assertTrue(got.persist)
    def test_tamper_recovers_from_backup_and_total_corruption_is_survivable(self):
        c = Core(self.root / "d"); c.load(); a = sp.new_site("A", "https://a.example.com"); c.sites.add(a); c.sites.save()
        b = sp.new_site("B", "https://b.example.com"); c.sites.add(b); c.sites.save()
        p = c.core_dir / "sites.xt"; d = bytearray(p.read_bytes()); d[30] ^= 0xFF; p.write_bytes(bytes(d))
        c2 = Core(self.root / "d"); self.assertEqual(c2.load()["sites"], "recovered"); self.assertIn(a.id, c2.sites.sites)
        for f in c2.core_dir.glob("sites.xt*"): f.write_bytes(b"x" * 90)
        c3 = Core(self.root / "d"); self.assertEqual(c3.load()["sites"], "corrupt"); self.assertEqual(c3.sites.sites, {})
    def test_invalid_stored_entries_are_dropped_not_trusted(self):
        c = Core(self.root / "d"); c.load()
        evil = [{"id": "ok1", "name": "Ok", "url": "https://example.com/"}, {"id": "bad1", "name": "Bad", "url": "http://localhost/admin"},
                {"id": "bad2", "name": "Bad2", "url": "https://example.com", "allow": ["doubleclick.net"]}, {"id": "bad3", "name": "B3", "url": "javascript:1"}, 5]
        c.sites.file.write(json.dumps({"sites": evil}).encode()); c2 = Core(self.root / "d"); c2.load()
        self.assertEqual(list(c2.sites.sites), ["ok1"])        # даже если файл подделан ключом, небезопасное не пройдёт
    def test_add_allow_rules(self):
        c = Core(self.root / "d"); c.load(); s = sp.new_site("S", "https://www.example.com"); c.sites.add(s)
        c.sites.add_allow(s.id, "static.example.net"); self.assertIn("static.example.net", s.allow)
        c.sites.add_allow(s.id, "example.com"); self.assertNotIn("example.com", s.allow)            # уже покрыт (www. отбрасывается)
        for bad in ("doubleclick.net", "localhost", "github.io", "127.0.0.1", "com"):
            with self.assertRaises(sp.SiteError, msg=bad): c.sites.add_allow(s.id, bad)
    def test_limits(self):
        c = Core(self.root / "d"); c.load()
        for i in range(sp.MAX_SITES): c.sites.add(sp.new_site(f"S{i}", f"https://s{i}.example.com"))
        with self.assertRaises(sp.SiteError): c.sites.add(sp.new_site("Лишний", "https://extra.example.com"))
    def test_remove_and_sources(self):
        c = Core(self.root / "d"); c.load(); m = sp.parse_site(MANIFEST); mine = sp.connect(m); c.sites.add(mine)
        self.assertEqual(c.sites.connected_sources(), {"demo"}); self.assertNotEqual(mine.id, "demo")
        self.assertIsNotNone(c.sites.remove(mine.id)); self.assertEqual(c.sites.connected_sources(), set()); self.assertIsNone(c.sites.remove("nope"))


class Catalog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.m = ex.ExtensionManager(self.root / "user", [ROOT / "extensions"]); self.m.scan()
    def tearDown(self): self.tmp.cleanup()
    def test_bundled_catalog(self):
        self.assertGreaterEqual(len(self.m.sites), 6); self.assertEqual(self.m.errors, [])
        for s in self.m.sites.values():
            self.assertTrue(s.url.startswith("https://")); self.assertFalse(s.persist, s.id)                  # каталог никогда не включает сохранение входа сам
            self.assertTrue(sp.decide("https", s.host, s.effective_allow()).ok, s.id); self.assertTrue(s.description, s.id)
    def test_catalog_has_no_trackers_or_wide_allows(self):
        for s in self.m.sites.values():
            for d in s.allow: self.assertFalse(sp.is_tracker(d)); self.assertIn(d.count("."), (1, 2), d)
    def test_install_site_manifest_and_remove(self):
        p = self.root / "m.json"; p.write_text(json.dumps(MANIFEST), encoding="utf-8"); n = len(self.m.sites)
        self.assertEqual(self.m.install_file(p), ["сайт «Демо»"]); self.assertEqual(len(self.m.sites), n + 1)
        self.assertTrue((self.root / "user/sites/demo.json").exists())
        self.assertTrue(self.m.remove("site", "demo")); self.assertNotIn("demo", self.m.sites)
        self.assertFalse(self.m.remove("site", "wikipedia-ru"))                                               # встроенные не удаляются
    def test_bad_manifest_rejected_and_nothing_written(self):
        for bad in ({**MANIFEST, "url": "http://192.168.0.1"}, {**MANIFEST, "allow": ["doubleclick.net"]}, {**MANIFEST, "url": "file:///etc/passwd"}):
            p = self.root / "bad.json"; p.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ex.ExtError): self.m.install_file(p)
        self.assertFalse((self.root / "user/sites").exists() and any((self.root / "user/sites").iterdir()))
    def test_pack_with_all_three_kinds(self):
        pack = {"type": "pack", "themes": [{"id": "pt", "name": "T", "colors": {"bg": "#101010", "text": "#EEEEEE", "accent": "#FF0066"}}],
                "accents": [{"id": "pa", "name": "A", "accent": "#00FF00"}], "sites": [MANIFEST]}
        p = self.root / "pack.json"; p.write_text(json.dumps(pack), encoding="utf-8")
        self.assertEqual(len(self.m.install_file(p)), 3); self.assertIn("pt", self.m.themes); self.assertIn("pa", self.m.accents); self.assertIn("demo", self.m.sites)
    def test_connect_copies_exact_permissions(self):
        m = sp.parse_site({**MANIFEST, "permissions": {"js": False, "persist": True, "fullscreen": False}}); c = sp.connect(m)
        self.assertEqual((c.js, c.persist, c.fullscreen, c.allow, c.url, c.source), (False, True, False, m.allow, m.url, "demo"))


if __name__ == "__main__":
    unittest.main()
