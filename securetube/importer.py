from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable, Optional

from .store import make_item, new_id
from .util import clean_title

CHUNK = 4 * 1024 * 1024
MIN_FREE = 200 * 1024 * 1024


class ImportFailed(Exception):
    """Сообщение уже написано по-человечески — его можно показывать как есть."""


class Cancelled(Exception):
    pass


def copy_file(src: Path, dst: Path, progress: Callable[[float], None],
              cancelled: Callable[[], bool]) -> None:
    total = src.stat().st_size
    free = shutil.disk_usage(dst.parent).free
    if free < total + MIN_FREE:
        raise ImportFailed("Недостаточно места на диске для копирования видео")
    done = 0
    try:
        with open(src, "rb") as fi, open(dst, "wb") as fo:
            while True:
                if cancelled():
                    raise Cancelled()
                buf = fi.read(CHUNK)
                if not buf:
                    break
                fo.write(buf)
                done += len(buf)
                progress(done / total if total else 1.0)
            fo.flush()
            os.fsync(fo.fileno())
        if dst.stat().st_size != total:
            raise ImportFailed("Файл скопирован не полностью — попробуйте ещё раз")
    except BaseException:
        try:
            dst.unlink()
        except OSError:
            pass
        raise


def import_one(src: Path, known: set, mode: str, media_dir: Path, delete_original: bool,
               progress: Callable[[float], None], cancelled: Callable[[], bool]) -> Optional[dict]:
    """Возвращает новый элемент или None, если видео уже в библиотеке."""
    try:
        size = src.stat().st_size
    except OSError:
        raise ImportFailed("Файл недоступен — возможно, он удалён или занят другой программой")
    if size <= 0:
        raise ImportFailed("Файл пустой")
    key = os.path.normcase(str(src))
    if key in known:
        return None
    if mode == "link":
        item = make_item(str(src), owned=False, orig=str(src), size=size, title=clean_title(src.name))
        progress(1.0)
        known.add(key)
        return item
    media_dir.mkdir(parents=True, exist_ok=True)
    iid = new_id()
    dst = media_dir / f"{iid}{src.suffix.lower()}"
    try:
        copy_file(src, dst, progress, cancelled)
    except PermissionError:
        raise ImportFailed("Нет доступа к файлу или папке библиотеки")
    except OSError as e:
        raise ImportFailed(f"Не удалось скопировать файл ({e.strerror or e})")
    item = make_item(str(dst), owned=True, orig=str(src), size=size, title=clean_title(src.name))
    item["id"] = iid
    known.add(key)
    if delete_original:
        try:
            src.unlink()
        except OSError:
            pass            
    return item
