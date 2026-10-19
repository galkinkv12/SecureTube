from __future__ import annotations

import colorsys
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from . import sitepolicy
from .fsutil import atomic_write
from .sitepolicy import Site, SiteError

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
KEYS = ("bg", "panel", "raised", "hover", "line", "line2", "text", "muted", "dim",
        "accent", "accent_hi", "accent2", "danger", "ok", "on_accent")
REQUIRED = ("bg", "text", "accent")
MAX_BYTES = 256 * 1024
MAX_ITEMS = 300
BUILTIN_ID = "securetube"
LEGACY_THEME_IDS = {"xxxtube": BUILTIN_ID}
TAGS = ("dark", "light")


class ExtError(Exception):
    """Сообщение написано для пользователя."""



def _rgb(h: str) -> Tuple[float, float, float]:
    h = h.lstrip("#")
    return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255


def _hex(r: float, g: float, b: float) -> str:
    c = lambda v: max(0, min(255, int(round(v * 255))))
    return f"#{c(r):02X}{c(g):02X}{c(b):02X}"


def mix(a: str, b: str, t: float) -> str:
    """t=0 -> a, t=1 -> b."""
    ra, ga, ba = _rgb(a)
    rb, gb, bb = _rgb(b)
    return _hex(ra + (rb - ra) * t, ga + (gb - ga) * t, ba + (bb - ba) * t)


def lum(h: str) -> float:
    def lin(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable_on(bg: str) -> str:
    return "#000000" if contrast(bg, "#000000") >= contrast(bg, "#FFFFFF") else "#FFFFFF"


def _rotate(h: str, deg: float) -> str:
    r, g, b = _rgb(h)
    hh, ll, ss = colorsys.rgb_to_hls(r, g, b)
    return _hex(*colorsys.hls_to_rgb((hh + deg / 360) % 1.0, ll, ss))


def derive(c: Dict[str, str]) -> Dict[str, str]:
    out = dict(c)
    bg, text, acc = out["bg"], out["text"], out["accent"]
    dark = lum(bg) < 0.3
    if dark:
        d = {"panel": mix(bg, text, .045), "raised": mix(bg, text, .085), "hover": mix(bg, text, .13),
             "line": mix(bg, text, .14), "line2": mix(bg, text, .24),
             "accent_hi": mix(acc, "#FFFFFF", .18), "danger": "#FF6B6B", "ok": "#46D488"}
    else:
        d = {"panel": mix(bg, "#FFFFFF", .7), "raised": mix(bg, "#FFFFFF", .85), "hover": mix(bg, text, .07),
             "line": mix(bg, text, .12), "line2": mix(bg, text, .22),
             "accent_hi": mix(acc, "#000000", .12), "danger": "#D93636", "ok": "#1E9E5A"}
    d.update({"muted": mix(text, bg, .42), "dim": mix(text, bg, .64),
              "accent2": _rotate(acc, 40), "on_accent": readable_on(acc)})
    for k, v in d.items():
        out.setdefault(k, v)
    return out


def with_accent(colors: Dict[str, str], accent: str, accent2: Optional[str] = None) -> Dict[str, str]:
    c = dict(colors)
    dark = lum(c["bg"]) < 0.3
    c["accent"] = accent
    c["accent_hi"] = mix(accent, "#FFFFFF", .18) if dark else mix(accent, "#000000", .12)
    c["on_accent"] = readable_on(accent)
    c["accent2"] = accent2 or _rotate(accent, 40)
    return c


@dataclass
class Theme:
    id: str
    name: str
    colors: Dict[str, str]
    radius: int = 14
    author: str = ""
    tags: List[str] = field(default_factory=list)
    source: str = "bundled"          
    path: Optional[Path] = None

    @property
    def dark(self) -> bool:
        return lum(self.colors["bg"]) < 0.3


@dataclass
class Accent:
    id: str
    name: str
    accent: str
    accent2: Optional[str] = None
    source: str = "bundled"
    path: Optional[Path] = None


BUILTIN = Theme(
    id=BUILTIN_ID, name="SecureTube", author="SecureTube", tags=["dark"], radius=14, source="builtin",
    colors={"bg": "#0C0D11", "panel": "#13151B", "raised": "#1A1D25", "hover": "#232733",
            "line": "#262A34", "line2": "#343947", "text": "#EDEFF4", "muted": "#8D94A6",
            "dim": "#5C6374", "accent": "#FF4D6D", "accent_hi": "#FF6B87", "accent2": "#7B61FF",
            "danger": "#FF6B6B", "ok": "#46D488", "on_accent": "#FFFFFF"})


def _color(v, key: str) -> str:
    if not isinstance(v, str) or not HEX.match(v):
        raise ExtError(f"Цвет «{key}» должен быть вида #RRGGBB")
    return v.upper()


def _text(v, limit: int, what: str, required: bool = True) -> str:
    if v is None and not required:
        return ""
    if not isinstance(v, str):
        raise ExtError(f"Поле «{what}» должно быть строкой")
    v = " ".join(v.split())
    if required and not v:
        raise ExtError(f"Поле «{what}» не заполнено")
    if len(v) > limit:
        raise ExtError(f"Поле «{what}» длиннее {limit} символов")
    return v


def parse_theme(obj, source: str = "user", path: Optional[Path] = None) -> Theme:
    if not isinstance(obj, dict):
        raise ExtError("Тема должна быть объектом JSON")
    tid = obj.get("id")
    if not isinstance(tid, str) or not ID.match(tid):
        raise ExtError("id темы: латиница в нижнем регистре, цифры, «-» и «_», до 40 символов")
    name = _text(obj.get("name"), 40, "name")
    raw = obj.get("colors")
    if not isinstance(raw, dict):
        raise ExtError("Нет блока colors")
    colors = {}
    for k, v in raw.items():
        if k in KEYS:
            colors[k] = _color(v, k)
    for k in REQUIRED:
        if k not in colors:
            raise ExtError(f"Не хватает цвета «{k}»")
    radius = obj.get("radius", 14)
    if isinstance(radius, bool) or not isinstance(radius, int):
        raise ExtError("radius должен быть целым числом от 0 до 28")
    radius = max(0, min(28, radius))
    full = derive(colors)
    tags = ["dark" if lum(full["bg"]) < 0.3 else "light"]
    return Theme(id=tid, name=name, colors=full, radius=radius,
                 author=_text(obj.get("author"), 40, "author", required=False), tags=tags,
                 source=source, path=path)


def parse_accent(obj, source: str = "user", path: Optional[Path] = None) -> Accent:
    if not isinstance(obj, dict):
        raise ExtError("Акцент должен быть объектом JSON")
    aid = obj.get("id")
    if not isinstance(aid, str) or not ID.match(aid):
        raise ExtError("id акцента: латиница в нижнем регистре, цифры, «-» и «_»")
    a2 = obj.get("accent2")
    return Accent(id=aid, name=_text(obj.get("name"), 40, "name"), accent=_color(obj.get("accent"), "accent"),
                  accent2=_color(a2, "accent2") if a2 is not None else None, source=source, path=path)


def parse_document(raw: bytes, source: str = "user", path: Optional[Path] = None):
    """-> (темы, акценты, ошибки по отдельным элементам). Сайты см. parse_document_ex."""
    themes, accents, _sites, errors = parse_document_ex(raw, source, path)
    return themes, accents, errors


def parse_document_ex(raw: bytes, source: str = "user", path: Optional[Path] = None):
    """-> (темы, акценты, сайты, ошибки по отдельным элементам)."""
    if len(raw) > MAX_BYTES:
        raise ExtError("Файл слишком большой для расширения (максимум 256 КБ)")
    try:
        doc = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        raise ExtError("Файл не читается: это не корректный JSON в кодировке UTF-8")
    if not isinstance(doc, dict):
        raise ExtError("Ожидался объект JSON")
    kind = doc.get("type", "theme" if "colors" in doc else ("site" if "url" in doc else ""))
    themes_raw, accents_raw, sites_raw = [], [], []
    if kind == "theme":
        themes_raw = [doc]
    elif kind == "accents":
        accents_raw = doc.get("items") or []
    elif kind == "pack":
        themes_raw, accents_raw = doc.get("themes") or [], doc.get("accents") or []
        sites_raw = doc.get("sites") or []
    elif kind == "site":
        sites_raw = [doc]
    elif kind == "sites":
        sites_raw = doc.get("items") or []
    else:
        raise ExtError("Неизвестный тип: ожидалось theme, accents, site или pack")
    if not isinstance(themes_raw, list) or not isinstance(accents_raw, list) or not isinstance(sites_raw, list):
        raise ExtError("Списки themes/accents/sites заданы неверно")
    if len(themes_raw) + len(accents_raw) + len(sites_raw) > MAX_ITEMS:
        raise ExtError(f"Слишком много элементов (максимум {MAX_ITEMS})")
    themes, accents, sites, errors = [], [], [], []
    for o in themes_raw:
        try:
            themes.append(parse_theme(o, source, path))
        except ExtError as e:
            errors.append(f"тема «{o.get('id', '?') if isinstance(o, dict) else '?'}»: {e}")
    for o in accents_raw:
        try:
            accents.append(parse_accent(o, source, path))
        except ExtError as e:
            errors.append(f"акцент «{o.get('id', '?') if isinstance(o, dict) else '?'}»: {e}")
    for o in sites_raw:
        try:
            sites.append(sitepolicy.parse_site(o))
        except SiteError as e:
            errors.append(f"сайт «{o.get('id', '?') if isinstance(o, dict) else '?'}»: {e}")
    return themes, accents, sites, errors


def theme_to_json(t: Theme) -> dict:
    explicit = {k: t.colors[k] for k in KEYS if k in t.colors}
    return {"type": "theme", "id": t.id, "name": t.name, "author": t.author,
            "tags": t.tags, "radius": t.radius, "colors": explicit}


def site_to_json(s: Site) -> dict:
    d = {"type": "site", "id": s.id, "name": s.name, "url": s.url, "allow": list(s.allow),
         "permissions": {"js": s.js, "persist": s.persist, "fullscreen": s.fullscreen}}
    if s.description:
        d["description"] = s.description
    return d


def accent_to_json(a: Accent) -> dict:
    d = {"type": "accents", "items": [{"id": a.id, "name": a.name, "accent": a.accent}]}
    if a.accent2:
        d["items"][0]["accent2"] = a.accent2
    return d


class ExtensionManager:
    def __init__(self, user_dir: Path, bundled_dirs: Iterable[Path] = ()):
        self.user_dir = Path(user_dir)
        self.bundled = [Path(p) for p in bundled_dirs]
        self.themes: Dict[str, Theme] = {}
        self.accents: Dict[str, Accent] = {}
        self.sites: Dict[str, Site] = {}                      
        self.site_origin: Dict[str, Tuple[str, Path]] = {}    
        self.errors: List[str] = []

    def scan(self) -> None:
        self.themes = {BUILTIN.id: BUILTIN}
        self.accents, self.errors = {}, []
        self.sites, self.site_origin = {}, {}
        seen = set()
        for root, source in [(b, "bundled") for b in self.bundled] + [(self.user_dir, "user")]:
            if not root.is_dir():
                continue
            for p in sorted(root.rglob("*.json")):
                key = str(p.resolve())
                if key in seen or p.is_symlink():
                    continue
                seen.add(key)
                try:
                    th, ac, st, errs = parse_document_ex(p.read_bytes(), source, p)
                except (ExtError, OSError) as e:
                    self.errors.append(f"{p.name}: {e}")
                    continue
                self.errors += [f"{p.name}, {e}" for e in errs]
                for t in th:
                    if t.id == BUILTIN_ID or t.id in LEGACY_THEME_IDS:
                        self.errors.append(f"{p.name}: id «{BUILTIN_ID}» зарезервирован")
                        continue
                    self.themes[t.id] = t
                for a in ac:
                    self.accents[a.id] = a
                for s in st:
                    self.sites[s.id] = s
                    self.site_origin[s.id] = (source, p)

    # --- выбор
    def theme(self, tid: str) -> Theme:
        return self.themes.get(LEGACY_THEME_IDS.get(tid, tid), BUILTIN)

    def catalog_sites(self) -> List[Site]:
        return list(self.sites.values())

    def accent(self, aid: str) -> Optional[Accent]:
        return self.accents.get(aid) if aid else None

    def ordered_themes(self) -> List[Theme]:
        return list(self.themes.values())

    def install_file(self, src: Path) -> List[str]:
        try:
            raw = Path(src).read_bytes()
        except OSError as e:
            raise ExtError(f"Не удалось прочитать файл: {e.strerror or e}")
        themes, accents, sites, errors = parse_document_ex(raw, "user")
        if not themes and not accents and not sites:
            raise ExtError(errors[0] if errors else "В файле нет тем, акцентов или сайтов")
        done = []
        for sub in ("themes", "accents", "sites"):
            (self.user_dir / sub).mkdir(parents=True, exist_ok=True)
        for t in themes:
            if t.id == BUILTIN_ID or t.id in LEGACY_THEME_IDS:
                raise ExtError(f"id «{t.id}» зарезервирован, выберите другой")
            atomic_write(self.user_dir / "themes" / f"{t.id}.json",
                         json.dumps(theme_to_json(t), ensure_ascii=False, indent=1).encode("utf-8"), private=False)
            done.append(f"тема «{t.name}»")
        for a in accents:
            atomic_write(self.user_dir / "accents" / f"{a.id}.json",
                         json.dumps(accent_to_json(a), ensure_ascii=False, indent=1).encode("utf-8"), private=False)
            done.append(f"акцент «{a.name}»")
        for s in sites:
            atomic_write(self.user_dir / "sites" / f"{s.id}.json",
                         json.dumps(site_to_json(s), ensure_ascii=False, indent=1).encode("utf-8"), private=False)
            done.append(f"сайт «{s.name}»")
        self.scan()
        return done

    def remove(self, kind: str, item_id: str) -> bool:
        if kind == "site":
            origin = self.site_origin.get(item_id)
            source, path = origin if origin else ("", None)
        else:
            item = self.themes.get(item_id) if kind == "theme" else self.accents.get(item_id)
            source, path = (item.source, item.path) if item else ("", None)
        if source != "user" or not path:
            return False
        try:
            path.resolve().relative_to(self.user_dir.resolve())
            path.unlink()
        except (OSError, ValueError):
            return False
        self.scan()
        return True
