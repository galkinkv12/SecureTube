import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from securetube import sitepolicy as sp


class Urls(unittest.TestCase):
    def test_normal_forms(self):
        for raw, want in (("example.com", "https://example.com/"), ("https://Example.COM/Path?q=1#frag", "https://example.com/Path?q=1"),
                          ("  https://ru.wikipedia.org  ", "https://ru.wikipedia.org/"), ("example.com.", "https://example.com/"),
                          ("https://example.com:443/x", "https://example.com/x")):
            self.assertEqual(sp.parse_url(raw).url, want, raw)
    def test_http_is_upgraded_with_warning(self):
        p = sp.parse_url("http://example.com/a"); self.assertTrue(p.url.startswith("https://")); self.assertTrue(p.warnings)
    def test_dangerous_schemes_rejected(self):
        for raw in ("javascript:alert(1)", "file:///C:/Windows/win.ini", "data:text/html,<script>1</script>", "ftp://example.com",
                    "chrome://settings", "about:blank", "blob:https://example.com/x", "view-source:https://example.com", "ws://example.com"):
            with self.assertRaises(sp.SiteError, msg=raw): sp.parse_url(raw)
    def test_phishing_tricks_rejected(self):
        for raw in ("https://google.com@evil.com", "https://user:pass@example.com", "https://evil.com\\@good.com",
                    "https://exa mple.com", "https://example.com/\x00", "https://example.com\t.evil.com", "https://good.com%40evil.com@x.com"):
            with self.assertRaises(sp.SiteError, msg=raw): sp.parse_url(raw)
    def test_local_and_ip_rejected(self):
        for raw in ("https://localhost", "https://127.0.0.1", "https://192.168.0.1", "https://10.0.0.5/admin", "https://[::1]/",
                    "https://169.254.169.254/latest/meta-data", "https://router.local", "https://nas.lan", "https://intranet",
                    "https://2130706433", "https://0x7f.1", "https://127.1", "https://8.8.8.8", "https://printer.home.arpa",
                    "https://[fe80::1]", "https://0.0.0.0", "https://hidden.onion", "https://foo.internal"):
            with self.assertRaises(sp.SiteError, msg=raw): sp.parse_url(raw)
    def test_ports_restricted(self):
        for raw in ("https://example.com:8443", "https://example.com:22", "https://example.com:80"):
            with self.assertRaises(sp.SiteError, msg=raw): sp.parse_url(raw)
    def test_garbage(self):
        for raw in ("", "   ", None, "https://", "https:///path", "https://.com", "https://-bad.com", "a" * 2100, "https://exa_mple.com"):
            with self.assertRaises(sp.SiteError, msg=str(raw)[:30]): sp.parse_url(raw)
    def test_idn_homograph_flagged_and_shown_as_punycode(self):
        p = sp.parse_url("https://аpple.com")            # первая «а» кириллическая
        self.assertTrue(p.host.startswith("xn--")); self.assertTrue(any("xn--" in w or "необычными" in w for w in p.warnings))
        self.assertEqual(sp.parse_url("https://пример.рф").host, "xn--e1afmkfd.xn--p1ai")
        self.assertEqual(sp.parse_url("https://example.com").warnings, [])


class Decisions(unittest.TestCase):
    A = ["wikipedia.org", "example.com"]
    def d(self, scheme, host, resource="other", allow=None): return sp.decide(scheme, host, self.A if allow is None else allow, resource)
    def test_allowed_and_subdomains(self):
        for h in ("wikipedia.org", "ru.wikipedia.org", "a.b.c.wikipedia.org", "EXAMPLE.com", "example.com."):
            self.assertTrue(self.d("https", h).ok, h)
    def test_lookalike_hosts_not_matched(self):
        for h in ("evilwikipedia.org", "wikipedia.org.evil.com", "wikipedia.org.evil", "xwikipedia.org", "example.com.attacker.net"):
            self.assertEqual(self.d("https", h).reason, "not_allowed", h)
    def test_scheme_rules(self):
        for s in ("http", "ws", "ftp", "file", "javascript", "chrome", "chrome-extension", "view-source", "filesystem"):
            self.assertEqual(self.d(s, "example.com").reason, "scheme", s)
        for s in ("https", "wss"): self.assertTrue(self.d(s, "example.com").ok)
        for s in ("data", "blob", "about", "qrc"): self.assertTrue(self.d(s, "").ok)
    def test_ip_private_and_empty(self):
        self.assertEqual(self.d("https", "").reason, "empty"); self.assertEqual(self.d("https", "93.184.216.34").reason, "ip")
        self.assertEqual(self.d("https", "192.168.1.1").reason, "ip"); self.assertEqual(self.d("https", "localhost").reason, "private")
        self.assertEqual(self.d("https", "[::1]").reason, "ip"); self.assertEqual(self.d("https", "example.lan").reason, "private")
    def test_private_never_allowed_even_if_listed(self):
        self.assertEqual(sp.decide("https", "localhost", ["localhost"]).reason, "private")
        self.assertEqual(sp.decide("https", "10.0.0.1", ["10.0.0.1"]).reason, "ip")
    def test_trackers_blocked_even_if_in_allow_list(self):
        for h in ("doubleclick.net", "stats.doubleclick.net", "www.google-analytics.com", "mc.yandex.ru", "connect.facebook.net"):
            self.assertEqual(sp.decide("https", h, [h, "doubleclick.net"]).reason, "tracker", h)
    def test_pings_blocked_even_on_allowed_host(self):
        self.assertEqual(self.d("https", "example.com", "ping").reason, "ping"); self.assertTrue(self.d("https", "example.com", "other").ok)
    def test_default_deny(self):
        self.assertEqual(sp.decide("https", "example.com", []).reason, "not_allowed")
    def test_hard_blocks_set(self):
        self.assertIn("tracker", sp.HARD_BLOCK); self.assertNotIn("not_allowed", sp.HARD_BLOCK)


class Allow(unittest.TestCase):
    def test_valid_and_dedup(self):
        self.assertEqual(sp.parse_allow("Example.com, www.example.org  example.com\nfoo.net"), ["example.com", "www.example.org", "foo.net"])
        self.assertEqual(sp.parse_allow(["*.example.com"]), ["example.com"]); self.assertEqual(sp.parse_allow(""), [])
    def test_rejected_entries(self):
        for bad in ("com", "*", "*.com", "localhost", "127.0.0.1", "github.io", "co.uk", "doubleclick.net", "evil..com", "a b", "ex@mple.com", "http://example.com/x"):
            with self.assertRaises(sp.SiteError, msg=bad): sp.parse_allow(bad)
    def test_limits_and_types(self):
        with self.assertRaises(sp.SiteError): sp.parse_allow([f"d{i}.example.com" for i in range(sp.MAX_ALLOW + 1)])
        with self.assertRaises(sp.SiteError): sp.parse_allow([1]); 
        with self.assertRaises(sp.SiteError): sp.parse_allow(5)
    def test_specific_subdomain_of_shared_host_is_ok(self):
        self.assertEqual(sp.parse_allow("user.github.io"), ["user.github.io"])


class Sites(unittest.TestCase):
    GOOD = {"id": "wiki", "name": "Википедия", "url": "https://ru.wikipedia.org", "allow": ["wikipedia.org", "wikimedia.org"],
            "permissions": {"js": True, "persist": False, "fullscreen": True}, "description": "Энциклопедия"}
    def test_parse_and_effective_allow(self):
        s = sp.parse_site(self.GOOD); self.assertEqual(s.host, "ru.wikipedia.org")
        self.assertEqual(s.effective_allow(), frozenset({"ru.wikipedia.org", "wikipedia.org", "wikimedia.org"}))
        self.assertEqual(sp.parse_site({**self.GOOD, "url": "https://www.example.com", "allow": []}).effective_allow(), frozenset({"www.example.com", "example.com"}))
    def test_roundtrip(self):
        s = sp.parse_site(self.GOOD); s2 = sp.parse_site(s.to_dict()); self.assertEqual(s, s2)
    def test_rejects_bad_manifests(self):
        bad = [{**self.GOOD, "url": "http://localhost"}, {**self.GOOD, "url": "javascript:1"}, {**self.GOOD, "allow": ["com"]},
               {**self.GOOD, "id": "../x"}, {**self.GOOD, "name": ""}, {**self.GOOD, "name": "x" * 50}, {**self.GOOD, "permissions": {"js": "yes"}},
               {**self.GOOD, "permissions": "all"}, {**self.GOOD, "description": "d" * 200}, [], "x", {**self.GOOD, "allow": "doubleclick.net"}]
        for b in bad:
            with self.assertRaises(sp.SiteError, msg=str(b)[:60]): sp.parse_site(b)
    def test_new_id_when_requested(self):
        a, b = sp.parse_site(self.GOOD, keep_id=False), sp.parse_site(self.GOOD, keep_id=False)
        self.assertNotEqual(a.id, b.id); self.assertNotEqual(a.id, "wiki")
    def test_unknown_fields_ignored_and_defaults_are_safe(self):
        s = sp.parse_site({"id": "x1", "name": "X", "url": "example.com", "evil": "<script>"})
        self.assertFalse(hasattr(s, "evil")); self.assertEqual((s.js, s.persist, s.fullscreen), (True, False, True))   # вход по умолчанию не сохраняется
    def test_permission_text_mentions_key_facts(self):
        text = "\n".join(sp.describe_permissions(sp.parse_site({**self.GOOD, "permissions": {"js": False, "persist": True}})))
        for must in ("ru.wikipedia.org", "wikimedia.org", "выключен", "не шифруются", "камера", "загрузка файлов"): self.assertIn(must, text)


if __name__ == "__main__":
    unittest.main()
