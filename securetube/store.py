from __future__ import annotations

import json
import os
import secrets
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .fsutil import atomic_write
from .sitepolicy import MAX_SITES, Site, SiteError, parse_site, validate_domain
from .util import VIDEO_EXTS, clean_title
from .vault import Vault, VaultError


def new_id() -> str:
    return secrets.token_hex(6)


class SecureFile:
    """чето важное, зашифрованное в хранилище. Может быть повреждено, тогда читается из резервной копии"""

    def __init__(self, path: Path, vault: Vault, label: str):
        self.path, self.vault, self.label = Path(path), vault, label
        self.bak = self.path.with_name(self.path.name + ".bak")
        self._main_ok = False

    def _decode(self, p: Path) -> bytes:
        return self.vault.open(p.read_bytes(), self.label)

    def read(self) -> Tuple[Optional[bytes], str]:
        """-> (данные|None, 'ok' | 'new' | 'recovered' | 'corrupt')"""
        if self.path.exists():
            try:
                data = self._decode(self.path)
                self._main_ok = True
                return data, "ok"
            except (VaultError, OSError):
                self._quarantine()
                if self.bak.exists():
                    try:
                        data = self._decode(self.bak)
                        return data, "recovered"
                    except (VaultError, OSError):
                        pass
                return None, "corrupt"
        if self.bak.exists():
            try:
                return self._decode(self.bak), "recovered"
            except (VaultError, OSError):
                return None, "corrupt"
        return None, "new"

    def _quarantine(self) -> None:
        try:
            os.replace(self.path, self.path.with_name(f"{self.path.name}.bad-{int(time.time())}"))
        except OSError:
            pass
        self._main_ok = False

    def write(self, data: bytes) -> None:
        if self._main_ok and self.path.exists():
            try:
                shutil.copyfile(self.path, self.bak)
            except OSError:
                pass
        atomic_write(self.path, self.vault.seal(data, self.label))
        self._main_ok = True


DEFAULTS = {
    "storage_mode": "copy",        
    "delete_originals": False,
    "media_dir": "",               
    "volume": 70,
    "muted": False,
    "sort": "added_desc",
    "card_size": 1,
    "autoplay_next": True,
    "remember_position": False,
    "lock_on_minimize": True,
    "idle_lock_min": 5,            
    "hide_from_capture": False,
    "sidebar_compact": False,
    "geometry": "",
    "theme": "securetube",
    "accent": "",
}
CHOICES = {
    "storage_mode": ("copy", "link"),
    "sort": ("added_desc", "added_asc", "title_asc", "title_desc", "dur_desc", "dur_asc", "size_desc"),
    "card_size": (0, 1, 2),
    "idle_lock_min": (0, 1, 5, 15),
}


def coerce(key: str, value):
    d = DEFAULTS[key]
    if key in CHOICES:
        return value if value in CHOICES[key] and not isinstance(value, bool) else d
    if isinstance(d, bool):
        return value if isinstance(value, bool) else d
    if isinstance(d, int):
        if isinstance(value, bool) or not isinstance(value, int):
            return d
        return max(0, min(100, value)) if key == "volume" else value
    return value if isinstance(value, str) else d


class Settings:
    def __init__(self, file: SecureFile):
        self.file = file
        self.data: Dict[str, object] = dict(DEFAULTS)
        self.status = "new"

    def load(self) -> str:
        raw, self.status = self.file.read()
        if raw is not None:
            try:
                obj = json.loads(raw.decode("utf-8"))
                if isinstance(obj, dict):
                    for k in DEFAULTS:
                        if k in obj:
                            self.data[k] = coerce(k, obj[k])
            except (ValueError, UnicodeDecodeError):
                self.status = "corrupt"
        return self.status

    def get(self, key: str):
        return self.data[key]

    def set(self, key: str, value, save: bool = True) -> None:
        self.data[key] = coerce(key, value)
        if save:
            self.save()

    def save(self) -> None:
        self.file.write(json.dumps(self.data, ensure_ascii=False).encode("utf-8"))


# ------------------------------------------------------------------ библиотека
def make_item(path: str, *, owned: bool, orig: str = "", title: str = "", size: int = 0) -> dict:
    return {"id": new_id(), "title": title or clean_title(path), "path": str(path),
            "owned": bool(owned), "orig": orig or str(path), "added": time.time(),
            "dur": 0, "size": int(size), "cat": "", "fav": False, "pos": 0,
            "th": False, "tf": 0}


_ITEM_TYPES = {"id": str, "title": str, "path": str, "owned": bool, "orig": str,
               "added": (int, float), "dur": int, "size": int, "cat": str,
               "fav": bool, "pos": int, "th": bool, "tf": int}


def _norm_item(raw) -> Optional[dict]:
    if not isinstance(raw, dict):
        return None
    base = make_item(str(raw.get("path", "")), owned=False)
    for k, t in _ITEM_TYPES.items():
        v = raw.get(k, base[k])
        if isinstance(v, bool) and t is not bool:
            v = base[k]
        base[k] = v if isinstance(v, t) else base[k]
    base["id"] = raw.get("id") if isinstance(raw.get("id"), str) and raw.get("id") else base["id"]
    return base if base["path"] else None


class Library:
    def __init__(self, file: SecureFile):
        self.file = file
        self.items: Dict[str, dict] = {}
        self.categories: List[str] = []
        self.status = "new"

    def load(self) -> str:
        raw, self.status = self.file.read()
        if raw is not None:
            try:
                obj = json.loads(raw.decode("utf-8"))
                for r in obj.get("items", []):
                    it = _norm_item(r)
                    if it:
                        self.items[it["id"]] = it
                cats = [c for c in obj.get("cats", []) if isinstance(c, str) and c.strip()]
                self.categories = list(dict.fromkeys(cats))
            except (ValueError, UnicodeDecodeError, AttributeError):
                self.items, self.categories, self.status = {}, [], "corrupt"
        return self.status

    def save(self) -> None:
        obj = {"v": 1, "cats": self.categories, "items": list(self.items.values())}
        self.file.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    # --- элементы
    def has_orig(self, orig: str) -> bool:
        key = os.path.normcase(orig)
        return any(os.path.normcase(i["orig"]) == key for i in self.items.values())

    def orig_set(self) -> set:
        return {os.path.normcase(i["orig"]) for i in self.items.values()}

    def add(self, item: dict) -> None:
        self.items[item["id"]] = item

    def remove(self, item_id: str) -> Optional[dict]:
        return self.items.pop(item_id, None)

    # --- категории
    def add_category(self, name: str) -> Optional[str]:
        name = " ".join(name.split())[:40]
        if not name or any(name.casefold() == c.casefold() for c in self.categories):
            return None
        self.categories.append(name)
        return name

    def rename_category(self, old: str, new: str) -> Optional[str]:
        new = " ".join(new.split())[:40]
        if old not in self.categories or not new:
            return None
        if new != old and any(new.casefold() == c.casefold() for c in self.categories):
            return None
        self.categories[self.categories.index(old)] = new
        for it in self.items.values():
            if it["cat"] == old:
                it["cat"] = new
        return new

    def delete_category(self, name: str) -> None:
        if name in self.categories:
            self.categories.remove(name)
        for it in self.items.values():
            if it["cat"] == name:
                it["cat"] = ""

    # --- восстановление: файлы в папке библиотеки, которых нет в индексе
    def adopt_orphans(self, media_dir: Path) -> List[dict]:
        known = {Path(i["path"]).name.casefold() for i in self.items.values() if i["owned"]}
        out = []
        try:
            entries = sorted(Path(media_dir).iterdir())
        except OSError:
            return out
        for p in entries:
            if p.is_file() and p.suffix.lower() in VIDEO_EXTS and p.name.casefold() not in known:
                try:
                    size = p.stat().st_size
                except OSError:
                    continue
                it = make_item(str(p), owned=True, orig="", title=f"Видео {len(self.items) + len(out) + 1}", size=size)
                it["id"] = p.stem if p.stem.isalnum() else it["id"]
                out.append(it)
                self.items[it["id"]] = it
        return out


class SiteBook:
    """Подключённые сайты. Хранятся зашифрованно, как и библиотека."""

    def __init__(self, file: SecureFile):
        self.file = file
        self.sites: Dict[str, Site] = {}
        self.status = "new"

    def load(self) -> str:
        raw, self.status = self.file.read()
        if raw is not None:
            try:
                for o in json.loads(raw.decode("utf-8")).get("sites", []):
                    try:                             
                        s = parse_site(o)
                        self.sites[s.id] = s
                    except SiteError:
                        continue
            except (ValueError, UnicodeDecodeError, AttributeError):
                self.sites, self.status = {}, "corrupt"
        return self.status

    def save(self) -> None:
        obj = {"v": 1, "sites": [s.to_dict() for s in self.sites.values()]}
        self.file.write(json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    def add(self, site: Site) -> None:
        if site.id not in self.sites and len(self.sites) >= MAX_SITES:
            raise SiteError(f"Слишком много сайтов (максимум {MAX_SITES})")
        self.sites[site.id] = site

    def remove(self, site_id: str) -> Optional[Site]:
        return self.sites.pop(site_id, None)

    def get(self, site_id: str) -> Optional[Site]:
        return self.sites.get(site_id)

    def add_allow(self, site_id: str, host: str) -> Site:
        """Разрешить ещё один домен. Рекламные и локальные адреса отклоняются проверкой."""
        site = self.sites[site_id]
        d = validate_domain(host)
        if d not in site.effective_allow():
            if len(site.allow) >= 20:
                raise SiteError("Слишком много разрешённых доменов (максимум 20)")
            site.allow.append(d)
        return site

    def connected_sources(self) -> set:
        return {s.source for s in self.sites.values() if s.source}


class ThumbStore:
    def __init__(self, directory: Path, vault: Vault):
        self.dir, self.vault = Path(directory), vault

    def _p(self, item_id: str) -> Path:
        return self.dir / f"{item_id}.xt"

    def save(self, item_id: str, jpeg: bytes) -> None:
        atomic_write(self._p(item_id), self.vault.seal(jpeg, "th:" + item_id))

    def load(self, item_id: str) -> Optional[bytes]:
        try:
            return self.vault.open(self._p(item_id).read_bytes(), "th:" + item_id)
        except (OSError, VaultError):
            return None

    def delete(self, item_id: str) -> None:
        try:
            self._p(item_id).unlink()
        except OSError:
            pass
