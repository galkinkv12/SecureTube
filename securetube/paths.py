from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_NAME


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    """Папка с программой (exe при сборке, иначе корень проекта:)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", app_dir()))
    return base.joinpath(*parts)


def hide_path(p: Path) -> None:
    """Windows: скрытая + системная папка (Проводник её не показывает!)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.kernel32.SetFileAttributesW(str(p), 0x2 | 0x4)
    except Exception:
        pass


def ensure_dir(p: Path, hidden: bool = True) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    if hidden:
        hide_path(p)
    return p


LEGACY_NAMES = ("XXXtube",) if os.name == "nt" else ("xxxtube",)


def _default_root() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local"))
        return base / APP_NAME
    base = Path(os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share"))
    return base / APP_NAME.lower()


def migrate_legacy(root: Path) -> Path:
    """Данные прежнего названия (XXXtube) переносятся в новую папку: библиотека, пароль и настройки сохраняются.

    Папка просто переименовывается, ничего не копируется и не расшифровывается.
    Если переименовать не удалось (занята другой программой), работаем со старой папкой.
    """
    if root.exists():
        return root
    for name in LEGACY_NAMES:
        old = root.parent / name
        if old.is_dir():
            try:
                os.replace(old, root)
                return root
            except OSError:
                return old
    return root


def data_root() -> Path:
    env = os.environ.get("SECURETUBE_HOME")
    root = Path(env) if env else migrate_legacy(_default_root())
    return ensure_dir(root)
