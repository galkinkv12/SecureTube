from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path

from .fsutil import atomic_write

MAX_FAILS = 3
BAN_SECONDS = 24 * 3600

SEED_SALT = bytes.fromhex("e30def7370691934cafbcc68e03cca19")
SEED_HASH = bytes.fromhex("d47bcde8f2bcfb6da0207c343ee115e9b1d5c3145b09eabda5df6d55e1ccffa4")
_N, _R, _P = 2 ** 14, 8, 1
MIN_PASSWORD = 8


def _derive(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=32)


class Auth:
    def __init__(self, data_dir: Path, key: bytes, first_run: bool):
        self.state_file = Path(data_dir) / "st.dat"
        self._key = key
        self._first_run = first_run
        if first_run and not self.state_file.exists():
            self._save(self._fresh(ban=False))

    # ---- хранилище ----
    def _sign(self, body: dict) -> str:
        data = json.dumps(body, sort_keys=True).encode()
        return hmac.new(self._key, data, hashlib.sha256).hexdigest()

    def _save(self, s: dict) -> None:
        s["last_seen"] = max(time.time(), s.get("last_seen", 0))
        body = {k: s[k] for k in ("salt", "hash", "fails", "ban_until", "last_seen")}
        atomic_write(self.state_file, json.dumps({**body, "sig": self._sign(body)}).encode())

    @staticmethod
    def _fresh(ban: bool) -> dict:
        now = time.time()
        return {"salt": SEED_SALT.hex(), "hash": SEED_HASH.hex(), "fails": 0,
                "ban_until": now + BAN_SECONDS if ban else 0.0, "last_seen": now}

    def _load(self) -> dict:
        try:
            raw = json.loads(self.state_file.read_text(encoding="utf-8"))
            sig = raw.pop("sig")
            if not hmac.compare_digest(sig, self._sign(raw)):
                raise ValueError("bad signature")
            return raw
        except Exception:
            s = self._fresh(ban=True)            
            self._save(s)
            return s

    @staticmethod
    def _now(s: dict) -> float:
        return max(time.time(), s.get("last_seen", 0))   

    # ---- API ----
    def ban_remaining(self) -> int:
        s = self._load()
        return max(0, int(s["ban_until"] - self._now(s)))

    def attempt(self, password: str):
        """-> ('ok', 0) | ('wrong', осталось_попыток) | ('banned', секунд)"""
        s = self._load()
        now = self._now(s)
        if now < s["ban_until"]:
            self._save(s)
            return "banned", int(s["ban_until"] - now)
        good = hmac.compare_digest(_derive(password, bytes.fromhex(s["salt"])),
                                   bytes.fromhex(s["hash"]))
        if good:
            s["fails"] = 0
            self._save(s)
            return "ok", 0
        s["fails"] += 1
        if s["fails"] >= MAX_FAILS:
            s["fails"] = 0
            s["ban_until"] = now + BAN_SECONDS
            self._save(s)
            return "banned", BAN_SECONDS
        self._save(s)
        return "wrong", MAX_FAILS - s["fails"]

    def set_password(self, old: str, new: str):
        """-> 'ok' | 'short' | 'wrong' | 'banned'"""
        if len(new) < MIN_PASSWORD:
            return "short"
        res, _ = self.attempt(old)
        if res != "ok":
            return res
        s = self._load()
        salt = secrets.token_bytes(16)
        s["salt"], s["hash"] = salt.hex(), _derive(new, salt).hex()
        self._save(s)
        return "ok"
