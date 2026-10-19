from __future__ import annotations

import datetime
import os
import re
import time
from pathlib import Path
from typing import Iterable, List

VIDEO_EXTS = {".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".ogv", ".wmv",
              ".flv", ".ts", ".mpg", ".mpeg", ".3gp"}
_NUM = re.compile(r"(\d+)")
_MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн",
           "июл", "авг", "сен", "окт", "ноя", "дек"]


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.casefold() for t in _NUM.split(s)]


def plural(n: int, forms) -> str:
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return forms[0]
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return forms[1]
    return forms[2]


def fmt_ms(ms: int) -> str:
    s = max(0, int(ms) // 1000)
    h, m, s = s // 3600, (s % 3600) // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def fmt_total(ms: int) -> str:
    m = max(0, int(ms) // 60000)
    h, m = divmod(m, 60)
    if h:
        return f"{h} ч {m} мин"
    return f"{max(m, 0)} мин"


def fmt_size(n: int) -> str:
    n = float(max(0, n))
    for unit in ("Б", "КБ", "МБ", "ГБ"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "Б" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} ТБ"


def fmt_ban(sec: int) -> str:
    h, m = sec // 3600, (sec % 3600) // 60
    return f"{h} ч {m} мин" if h else f"{max(1, m)} мин"


def fmt_added(ts: float, now: float | None = None) -> str:
    now = time.time() if now is None else now
    d0 = datetime.date.fromtimestamp(ts)
    days = (datetime.date.fromtimestamp(now) - d0).days
    if days <= 0:
        return "сегодня"
    if days == 1:
        return "вчера"
    if days < 7:
        return f"{days} {plural(days, ('день', 'дня', 'дней'))} назад"
    return f"{d0.day} {_MONTHS[d0.month - 1]} {d0.year}"


def clean_title(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[_.]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip()
    return stem or name


def is_video(p: Path) -> bool:
    return p.suffix.lower() in VIDEO_EXTS


def scan(paths: Iterable) -> List[Path]:
    """Файлы и папки -> список видеофайлов (папки обходятся рекурсивно)."""
    out: List[Path] = []
    seen = set()

    def push(p: Path):
        key = os.path.normcase(str(p.resolve()))
        if key not in seen:
            seen.add(key)
            out.append(p)

    for raw in paths:
        p = Path(raw)
        try:
            if p.is_symlink():
                continue
            if p.is_file():
                if is_video(p):
                    push(p)
            elif p.is_dir():
                found = []
                for root, dirs, files in os.walk(p, followlinks=False):
                    dirs[:] = [d for d in dirs if not d.startswith(".")]
                    for f in files:
                        fp = Path(root) / f
                        if not f.startswith(".") and is_video(fp) and not fp.is_symlink():
                            found.append(fp)
                found.sort(key=lambda x: natural_key(str(x)))
                for fp in found:
                    push(fp)
        except OSError:
            continue
    return out
