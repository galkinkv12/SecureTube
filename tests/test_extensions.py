import json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from securetube import extensions as ex

ROOT = Path(__file__).resolve().parent.parent
GOOD = {"type": "theme", "id": "mine", "name": "Моя", "colors": {"bg": "#101010", "text": "#EEEEEE", "accent": "#FF0066"}}


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        self.m = ex.ExtensionManager(self.root / "user", [ROOT / "extensions"])
    def tearDown(self): self.tmp.cleanup()
    def doc(self, obj, name="x.json"):
        p = self.root / name; p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8"); return p

    def test_color_math(self):
        self.assertEqual(ex.mix("#000000", "#FFFFFF", .5), "#808080"); self.assertEqual(ex.mix("#102030", "#FFFFFF", 0), "#102030")
        self.assertAlmostEqual(ex.contrast("#000000", "#FFFFFF"), 21.0, 1); self.assertEqual(ex.readable_on("#FFFF00"), "#000000")
        self.assertEqual(ex.readable_on("#101010"), "#FFFFFF")
    def test_derive_fills_every_key_with_valid_hex(self):
        for c in ({"bg": "#101010", "text": "#EEEEEE", "accent": "#FF0066"}, {"bg": "#FAFAFA", "text": "#222222", "accent": "#0066FF"}):
            full = ex.derive(c)
            self.assertEqual(set(full), set(ex.KEYS)); self.assertTrue(all(ex.HEX.match(v) for v in full.values()))
    def test_explicit_keys_not_overridden(self):
        self.assertEqual(ex.derive({"bg": "#101010", "text": "#EEEEEE", "accent": "#FF0066", "panel": "#123456"})["panel"], "#123456")
    def test_accent_override(self):
        base = ex.derive(GOOD["colors"]); c = ex.with_accent(base, "#FFFF00")
        self.assertEqual(c["accent"], "#FFFF00"); self.assertEqual(c["on_accent"], "#000000"); self.assertEqual(c["bg"], base["bg"])

    def test_validation_rejects_bad_input(self):
        bad = [
            {**GOOD, "colors": {**GOOD["colors"], "bg": "#fff"}},                                   # короткий цвет
            {**GOOD, "colors": {**GOOD["colors"], "bg": "#101010;} QWidget{background:red"}},       # попытка внедрить QSS
            {**GOOD, "colors": {**GOOD["colors"], "text": "url(http://evil)"}},
            {**GOOD, "id": "../../evil"}, {**GOOD, "id": "UPPER"}, {**GOOD, "id": ""},
            {**GOOD, "name": "x" * 100}, {**GOOD, "name": ""}, {**GOOD, "radius": "big"}, {**GOOD, "radius": True},
            {**GOOD, "colors": {"bg": "#101010"}}, {**GOOD, "colors": "nope"}, [1, 2], "str"]
        for b in bad:
            with self.assertRaises(ex.ExtError, msg=str(b)): ex.parse_theme(b)
    def test_radius_clamped_unknown_keys_ignored(self):
        t = ex.parse_theme({**GOOD, "radius": 999, "evil": "x", "colors": {**GOOD["colors"], "hax": "#000000"}})
        self.assertEqual(t.radius, 28); self.assertNotIn("hax", t.colors)
    def test_document_limits(self):
        with self.assertRaises(ex.ExtError): ex.parse_document(b"x" * (ex.MAX_BYTES + 1))
        with self.assertRaises(ex.ExtError): ex.parse_document(b"{not json")
        with self.assertRaises(ex.ExtError): ex.parse_document(b'{"type":"script","code":"os.system"}')
        with self.assertRaises(ex.ExtError): ex.parse_document(b"\xff\xfe\x00")
        big = {"type": "pack", "themes": [{**GOOD, "id": f"t{i}"} for i in range(ex.MAX_ITEMS + 1)]}
        with self.assertRaises(ex.ExtError): ex.parse_document(json.dumps(big).encode())
    def test_pack_partial_errors_reported(self):
        th, ac, errs = ex.parse_document(json.dumps({"type": "pack", "themes": [GOOD, {"id": "bad"}], "accents": [{"id": "a", "name": "A", "accent": "#123456"}, {"id": "b"}]}).encode())
        self.assertEqual((len(th), len(ac), len(errs)), (1, 1, 2))

    # ---- поставляемый набор
    def test_shipped_pack(self):
        self.m.scan(); themes = self.m.ordered_themes()
        self.assertGreaterEqual(len(themes), 60); self.assertEqual(self.m.errors, [])
        ids = [t.id for t in themes]; self.assertEqual(len(ids), len(set(ids))); self.assertEqual(themes[0].id, ex.BUILTIN_ID)
        self.assertGreaterEqual(len(self.m.accents), 18)
        self.assertGreaterEqual(sum(t.dark for t in themes), 30); self.assertGreaterEqual(sum(not t.dark for t in themes), 12)
    def test_shipped_pack_readability(self):
        self.m.scan(); weak = []
        for t in self.m.ordered_themes():
            c = t.colors
            if t.source == "builtin":      # фирменная тема из первой версии: белый на розовом ≈3,4:1, оставлена как есть
                continue
            if ex.contrast(c["text"], c["bg"]) < 7 or ex.contrast(c["text"], c["panel"]) < 6.5 or ex.contrast(c["on_accent"], c["accent"]) < 4.5 or ex.contrast(c["accent"], c["bg"]) < 3:
                weak.append(t.id)
            for k in ex.KEYS: self.assertTrue(ex.HEX.match(c[k]), (t.id, k))
        self.assertEqual(weak, [])
    def test_accents_valid_with_every_theme(self):
        self.m.scan()
        for a in self.m.accents.values():
            for t in self.m.ordered_themes()[:5]:
                c = ex.with_accent(t.colors, a.accent, a.accent2); self.assertTrue(all(ex.HEX.match(v) for v in c.values()))

    # ---- установка пользователя
    def test_install_theme_and_use(self):
        self.m.scan(); n0 = len(self.m.themes); done = self.m.install_file(self.doc(GOOD))
        self.assertEqual(done, ["тема «Моя»"]); self.assertEqual(len(self.m.themes), n0 + 1)
        self.assertEqual(self.m.theme("mine").source, "user"); self.assertTrue((self.root / "user/themes/mine.json").exists())
        m2 = ex.ExtensionManager(self.root / "user", [ROOT / "extensions"]); m2.scan(); self.assertIn("mine", m2.themes)   # переживает перезапуск
    def test_install_normalizes_file(self):
        self.m.install_file(self.doc({**GOOD, "evil": "<script>", "colors": {**GOOD["colors"], "hax": "#000000"}}))
        saved = json.loads((self.root / "user/themes/mine.json").read_text(encoding="utf-8"))
        self.assertNotIn("evil", saved); self.assertNotIn("hax", saved["colors"])
    def test_install_rejects_builtin_id_and_garbage(self):
        with self.assertRaises(ex.ExtError): self.m.install_file(self.doc({**GOOD, "id": ex.BUILTIN_ID}))
        with self.assertRaises(ex.ExtError): self.m.install_file(self.doc({"type": "theme", "id": "x"}))
        with self.assertRaises(ex.ExtError): self.m.install_file(self.root / "missing.json")
        self.assertFalse((self.root / "user/themes").exists() and any((self.root / "user/themes").iterdir()))
    def test_install_accent_pack_and_remove(self):
        self.m.install_file(self.doc({"type": "accents", "items": [{"id": "z", "name": "Зет", "accent": "#00FF00"}]}))
        self.assertIn("z", self.m.accents); self.assertTrue(self.m.remove("accent", "z")); self.assertNotIn("z", self.m.accents)
    def test_remove_only_user_items(self):
        self.m.scan(); self.assertFalse(self.m.remove("theme", "midnight")); self.assertFalse(self.m.remove("theme", ex.BUILTIN_ID))
        self.assertTrue((ROOT / "extensions/themes").glob("*midnight*").__next__().exists())
        self.m.install_file(self.doc(GOOD)); self.assertTrue(self.m.remove("theme", "mine")); self.assertNotIn("mine", self.m.themes)
    def test_user_theme_overrides_bundled_and_broken_files_reported(self):
        self.m.install_file(self.doc({**GOOD, "id": "midnight", "name": "Моя полночь"})); self.assertEqual(self.m.theme("midnight").name, "Моя полночь")
        (self.root / "user" / "themes" / "broken.json").write_text("{oops", encoding="utf-8"); self.m.scan()
        self.assertTrue(any("broken.json" in e for e in self.m.errors)); self.assertIn("midnight", self.m.themes)
    def test_unknown_ids_fall_back(self):
        self.m.scan(); self.assertEqual(self.m.theme("nope").id, ex.BUILTIN_ID); self.assertIsNone(self.m.accent("nope")); self.assertIsNone(self.m.accent(""))


if __name__ == "__main__":
    unittest.main()
