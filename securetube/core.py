from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from . import paths
from .auth import Auth
from .extensions import ExtensionManager
from .keystore import KeyStore, KeyUnavailable
from .store import Library, SecureFile, SiteBook, Settings, ThumbStore
from .vault import Vault

__all__ = ["Core", "KeyUnavailable", "reset_keys"]


class Core:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else paths.data_root()
        paths.ensure_dir(self.root)
        self.core_dir = paths.ensure_dir(self.root / "core")
        self.cache_dir = paths.ensure_dir(self.root / "cache")
        self.default_media = paths.ensure_dir(self.root / "media")
        self.keys = KeyStore(self.core_dir / "kk.bin")
        self.keys.load()                                   
        self.vault = Vault(self.keys.subkey("vault"))
        self.auth = Auth(self.core_dir, self.keys.subkey("auth"), first_run=self.keys.created)
        self.settings = Settings(SecureFile(self.core_dir / "cfg.xt", self.vault, "cfg"))
        self.library = Library(SecureFile(self.core_dir / "lib.xt", self.vault, "lib"))
        self.sites = SiteBook(SecureFile(self.core_dir / "sites.xt", self.vault, "sites"))
        self.thumbs = ThumbStore(self.cache_dir, self.vault)
        self.ext = ExtensionManager(self.root / "ext", [paths.resource("extensions")])

    def load(self) -> dict:
        """Загружает настройки и библиотеку; возвращает статусы для сообщений."""
        return {"settings": self.settings.load(), "library": self.library.load(), "sites": self.sites.load()}

    def media_dir(self) -> Path:
        custom = str(self.settings.get("media_dir") or "")
        p = Path(custom) if custom else self.default_media
        try:
            return paths.ensure_dir(p, hidden=not custom)
        except OSError:
            return paths.ensure_dir(self.default_media)


def reset_keys(root: Optional[Path] = None) -> None:
    """Начать заново, если ключ не читается. Видео в папке media не трогаем."""
    root = Path(root) if root else paths.data_root()
    for name in ("core", "cache"):
        shutil.rmtree(root / name, ignore_errors=True)
