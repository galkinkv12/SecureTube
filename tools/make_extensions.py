import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from securetube import extensions as ex

# id, название, bg, text, accent, accent2, радиус (None = стандартный)
DARK = [
    ("midnight", "Полночь", "#0B0F1A", "#E6EAF5", "#5B8CFF", "#A78BFA", None),
    ("graphite", "Графит", "#121212", "#ECECEC", "#FF8A3D", "#FFC857", None),
    ("charcoal", "Уголь", "#16181D", "#E8E9ED", "#4DD0C4", "#7DE3A5", None),
    ("cosmos", "Космос", "#0A0614", "#EDE7FF", "#B66DFF", "#FF5DA2", None),
    ("ocean", "Океан", "#071A24", "#DFF3F8", "#22C1E6", "#3BE0B2", None),
    ("forest", "Лес", "#0C1710", "#E3F1E6", "#5FD17A", "#C8E86B", None),
    ("bordeaux", "Бордо", "#190A10", "#F6E4E9", "#E8436B", "#FF9E6D", None),
    ("coffee", "Кофе", "#17110D", "#F1E7DE", "#D9A066", "#A86A3B", None),
    ("dusk", "Сумерки", "#17121F", "#EEE7F7", "#FF7AA8", "#8E7CFF", None),
    ("neon", "Неон", "#07070D", "#F0F0FF", "#00F0FF", "#FF2BD6", None),
    ("cyberpunk", "Киберпанк", "#0D0A12", "#F3F0D9", "#FCEE0A", "#FF2A6D", None),
    ("synthwave", "Синтвейв", "#1A1033", "#F4E9FF", "#FF4FD8", "#3DE8FF", None),
    ("mint-night", "Мята ночью", "#0A1514", "#E1F5F0", "#3EE0B5", "#66B7FF", None),
    ("lavender-night", "Лаванда ночью", "#14111C", "#ECE6F6", "#B392F0", "#F28FBE", None),
    ("gold", "Золото", "#0F0D08", "#F3EAD2", "#E6B84D", "#F08A4B", None),
    ("dracula", "Дракула", "#282A36", "#F8F8F2", "#BD93F9", "#FF79C6", None),
    ("nord", "Нордик", "#2E3440", "#ECEFF4", "#88C0D0", "#81A1C1", None),
    ("gruvbox-dark", "Груввокс", "#1D2021", "#EBDBB2", "#FABD2F", "#FE8019", None),
    ("solarized-dark", "Солнечная тень", "#002B36", "#EEE8D5", "#268BD2", "#2AA198", None),
    ("monokai", "Монокай", "#1E1F1C", "#F8F8F2", "#A6E22E", "#F92672", None),
    ("one-dark", "Атом", "#1E2127", "#D7DAE0", "#61AFEF", "#C678DD", None),
    ("tokyo-night", "Токио-ночь", "#16161E", "#C0CAF5", "#7AA2F7", "#BB9AF7", None),
    ("mocha", "Мокка", "#11111B", "#CDD6F4", "#CBA6F7", "#F5C2E7", None),
    ("rose-pine", "Сосна и роза", "#191724", "#E0DEF4", "#EB6F92", "#C4A7E7", None),
    ("everforest", "Вечный лес", "#1E2326", "#D3C6AA", "#A7C080", "#DBBC7F", None),
    ("mirage", "Мираж", "#1F2430", "#CCCAC2", "#FFCC66", "#73D0FF", None),
    ("hub-dark", "Хаб тёмный", "#0D1117", "#E6EDF3", "#2F81F7", "#3FB950", None),
    ("material-ocean", "Материал", "#0F111A", "#D6DAEC", "#82AAFF", "#C3E88D", None),
    ("nightfox", "Ночная лиса", "#131A24", "#CDCECF", "#719CD6", "#9D79D6", None),
    ("amoled", "AMOLED", "#000000", "#F2F2F2", "#FF3B5C", "#7B61FF", None),
    ("amoled-blue", "AMOLED синий", "#000000", "#EAF2FF", "#3D8BFF", "#2DD4FF", None),
    ("amoled-green", "AMOLED зелёный", "#000000", "#E8FFF0", "#2EE66B", "#B6FF3D", None),
    ("blood-moon", "Кровавая луна", "#120405", "#F7E3E1", "#E02D2D", "#FF7A45", None),
    ("matrix", "Матрица", "#020A04", "#CFFFD8", "#00FF66", "#00B84A", None),
    ("amber", "Янтарный терминал", "#0F0A02", "#FFD79A", "#FFB000", "#FF7A00", None),
    ("cinema", "Кино", "#140E0C", "#F3E6D8", "#E5533D", "#F2A541", None),
    ("aurora", "Аврора", "#0A1220", "#E4F4F6", "#52E0B6", "#8A7CFF", None),
    ("deep-sea", "Глубокое море", "#031318", "#D8F1F2", "#1EA7A8", "#62D2E8", None),
    ("volcano", "Вулкан", "#160A06", "#F6E2D8", "#FF5A1F", "#FFB020", None),
    ("taiga", "Тайга", "#0E1512", "#DDE9E1", "#7FB08A", "#C9A66B", None),
    ("desert-night", "Пустыня ночью", "#181210", "#F0E3D3", "#E0A15B", "#C96F5A", None),
    ("mojito", "Мохито", "#08150F", "#E6F6EC", "#7BE495", "#F4F269", None),
    ("whisky", "Виски", "#1A110A", "#F4E5D1", "#E39B45", "#B5651D", None),
    ("tokyo-city", "Ночной город", "#0B0B16", "#F1E9F6", "#FF5C8A", "#4DD6FF", None),
    ("slate", "Сланец", "#13181F", "#E2E8F0", "#38BDF8", "#818CF8", None),
    ("plum", "Слива", "#170B17", "#F5E6F3", "#D45BB3", "#7C5CFF", None),
    ("mono", "Монохром", "#0B0B0B", "#EDEDED", "#FFFFFF", "#9A9A9A", None),
    ("emerald", "Изумруд", "#07140F", "#E2F5EC", "#10B981", "#34D399", None),
    ("sapphire", "Сапфир", "#060D1F", "#E3EAFB", "#3B6FF5", "#7CA3FF", None),
    ("ruby", "Рубин", "#14060A", "#F8E3E8", "#E11D48", "#FB7185", None),
    ("amethyst", "Аметист", "#100818", "#EEE6FA", "#9B5DE5", "#F15BB5", None),
    ("citrine", "Цитрин", "#14110A", "#F7F0D8", "#F5C518", "#FF9F1C", None),
    ("brutal-dark", "Брутализм ночью", "#0E0E0E", "#F2F2F2", "#C6FF00", "#FF3B00", 0),
    ("bubble-night", "Пузырь", "#14122B", "#ECEBFF", "#FF6EC7", "#6EA8FF", 24),
]
LIGHT = [
    ("snow", "Снег", "#F4F6FA", "#14171F", "#E0294F", "#6A4DFF", None),
    ("paper", "Бумага", "#F6F1E7", "#2B2620", "#B8481F", "#7A5A2B", None),
    ("sakura", "Сакура", "#FBF3F5", "#3A2530", "#D13E73", "#8A5CF0", None),
    ("mint-light", "Мята", "#EEF8F4", "#12302A", "#13806A", "#2B6FD6", None),
    ("sky", "Небо", "#EEF5FC", "#11263D", "#1F6FDB", "#2B9BD6", None),
    ("sand", "Песок", "#F7F0E3", "#3A2E1F", "#A9620B", "#8F4A12", None),
    ("lemon", "Лимон", "#FBF9E6", "#2E2B12", "#9C7F00", "#6E8F00", None),
    ("peach", "Персик", "#FFF3EC", "#3A2218", "#E8552B", "#D63A67", None),
    ("solarized-light", "Солнечный день", "#FDF6E3", "#25333A", "#268BD2", "#2AA198", None),
    ("hub-light", "Хаб светлый", "#F6F8FA", "#1F2328", "#0969DA", "#1A7F37", None),
    ("latte", "Латте", "#EFF1F5", "#2F3150", "#8839EF", "#EA76CB", None),
    ("rose-dawn", "Рассвет розы", "#FAF4ED", "#3A3556", "#B4637A", "#907AA9", None),
    ("gruvbox-light", "Груввокс светлый", "#FBF1C7", "#2C2827", "#B57614", "#AF3A03", None),
    ("lavender", "Лаванда", "#F5F2FB", "#2A2140", "#6A47F0", "#B24BC0", None),
    ("ayu-light", "Айю светлый", "#FAFAFA", "#313846", "#E36D00", "#2D86C0", None),
    ("brutal", "Брутализм", "#F2F0E6", "#111111", "#E03200", "#0038FF", 0),
    ("candy", "Конфета", "#FFF1F8", "#3B1F33", "#E0357F", "#7A5CF0", 24),
]
ACCENTS = [
    ("coral", "Коралл", "#FF6B6B"), ("rose", "Роза", "#FF4D6D"), ("raspberry", "Малина", "#E11D48"),
    ("orange", "Оранж", "#FF8A3D"), ("amber", "Янтарь", "#FFB000"), ("lemon", "Лимон", "#FACC15"),
    ("lime", "Лайм", "#A3E635"), ("green", "Зелёный", "#46D488"), ("teal", "Мята", "#2DD4BF"),
    ("cyan", "Бирюза", "#22D3EE"), ("sky", "Небо", "#38BDF8"), ("blue", "Синий", "#3B82F6"),
    ("indigo", "Индиго", "#6366F1"), ("violet", "Фиолет", "#8B5CF6"), ("fuchsia", "Пурпур", "#D946EF"),
    ("pink", "Розовый", "#F472B6"), ("silver", "Серебро", "#CBD5E1"), ("gold", "Золото", "#E6B84D"),
    ("white", "Белый", "#FFFFFF"), ("crimson", "Багрянец", "#DC143C"),
]


SITES = [
    ("wikipedia-ru", "Википедия", "https://ru.wikipedia.org", ["wikipedia.org", "wikimedia.org"],
     "Свободная энциклопедия. Картинки грузятся с wikimedia.org, он уже разрешён."),
    ("wikipedia-en", "Wikipedia (EN)", "https://en.wikipedia.org", ["wikipedia.org", "wikimedia.org"],
     "Английская Википедия."),
    ("wikimedia-commons", "Викисклад", "https://commons.wikimedia.org", ["wikimedia.org", "wikipedia.org"],
     "Свободные изображения, видео и звуки."),
    ("hacker-news", "Hacker News", "https://news.ycombinator.com", ["ycombinator.com"],
     "Новости IT. Внешние ссылки блокируются: их можно открыть во внешнем браузере после подтверждения."),
    ("internet-archive", "Internet Archive", "https://archive.org", ["archive.org"],
     "Библиотека книг, фильмов и сайтов. Если что-то не грузится, разрешите домен через щит."),
    ("openstreetmap", "OpenStreetMap", "https://www.openstreetmap.org", ["openstreetmap.org"],
     "Свободная карта мира. Плитки карты грузятся с домена openstreetmap.org."),
    ("example", "Проверка (example.com)", "https://example.com", ["example.com"],
     "Пустая тестовая страница: удобно проверить, что раздел «Сайты» работает."),
]


def build(out: Path):
    tdir = out / "themes"
    tdir.mkdir(parents=True, exist_ok=True)
    for f in tdir.glob("*.json"):
        f.unlink()
    n = 0
    for group in (DARK, LIGHT):
        for tid, name, bg, text, acc, acc2, radius in group:
            n += 1
            doc = {"type": "theme", "id": tid, "name": name, "author": "SecureTube",
                   "colors": {"bg": bg, "text": text, "accent": acc, "accent2": acc2}}
            if radius is not None:
                doc["radius"] = radius
            (tdir / f"{n:03d}_{tid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    sdir = out / "sites"
    sdir.mkdir(parents=True, exist_ok=True)
    for f in sdir.glob("*.json"):
        f.unlink()
    for i, (sid, name, url, allow, desc) in enumerate(SITES, 1):
        doc = {"type": "site", "id": sid, "name": name, "url": url, "allow": allow, "description": desc,
               "permissions": {"js": True, "persist": False, "fullscreen": True}}
        (sdir / f"{i:02d}_{sid}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "accents.json").write_text(json.dumps(
        {"type": "accents", "items": [{"id": i, "name": n_, "accent": c} for i, n_, c in ACCENTS]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return n


def quality(out: Path):
    """Проверка читаемости: возвращает список замечаний."""
    bad = []
    th, ac, errs = [], [], []
    for p in sorted((out / "themes").glob("*.json")):
        t, a, e = ex.parse_document(p.read_bytes()); th += t; errs += e
    for t in th:
        c = t.colors
        checks = (("текст/фон", ex.contrast(c["text"], c["bg"]), 7.0), ("приглушённый/фон", ex.contrast(c["muted"], c["bg"]), 3.2),
                  ("текст/панель", ex.contrast(c["text"], c["panel"]), 6.5), ("акцент/фон", ex.contrast(c["accent"], c["bg"]), 3.0),
                  ("на акценте", ex.contrast(c["on_accent"], c["accent"]), 4.5), ("муть/панель", ex.contrast(c["muted"], c["panel"]), 3.0),
                  ("линия/фон", ex.contrast(c["line2"], c["bg"]), 1.2))
        for what, got, need in checks:
            if got < need:
                bad.append(f"{t.id}: {what} {got:.2f} < {need}")
    return th, errs, bad


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "extensions"
    n = build(out)
    th, errs, bad = quality(out)
    from securetube.extensions import ExtensionManager
    m = ExtensionManager(Path("/tmp/_x_sites"), [out]); m.scan()
    print(f"сайтов-коннекторов: {len(m.sites)}, ошибок: {len(m.errors)}")
    print(f"тем: {n}, загружено: {len(th)}, ошибок разбора: {len(errs)}, замечаний по контрасту: {len(bad)}")
    print("\n".join(errs + bad))
