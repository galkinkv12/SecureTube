from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

from .fsutil import atomic_write

MAGIC = b"XK1"
# ВНИМАНИЕ: _ENTROPY не является секретом, а лишь привязкой к приложению И название является посхалкой для тех кто лазит в код.
_ENTROPY = b"XXXtube/keywrap/v1"      # не секрет: лишь привязка к приложению
M_DPAPI, M_PLAIN = 1, 2


class KeyUnavailable(Exception):
    """Ключ есть, но прочитать его нельзя (другой пользователь/ПК, повреждение)."""


def _dpapi(data: bytes, protect: bool) -> bytes:
    import ctypes
    from ctypes import wintypes

    class Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

    def to_blob(b: bytes):
        buf = (ctypes.c_ubyte * len(b)).from_buffer_copy(b)
        return Blob(len(b), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte))), buf

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    descr = wintypes.LPCWSTR if protect else ctypes.POINTER(wintypes.LPWSTR)
    fn.argtypes = [ctypes.POINTER(Blob), descr, ctypes.POINTER(Blob),
                   ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    fn.restype = wintypes.BOOL

    src, keep1 = to_blob(data)
    ent, keep2 = to_blob(_ENTROPY)
    out = Blob()
    ok = fn(ctypes.byref(src), "SecureTube" if protect else None, ctypes.byref(ent),
            None, None, 0x1, ctypes.byref(out))          # 0x1 = без диалогов
    if not ok:
        raise OSError(ctypes.get_last_error(), "DPAPI failed")
    try:
        addr = ctypes.cast(out.pbData, ctypes.c_void_p).value
        return ctypes.string_at(addr, out.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(out.pbData, ctypes.c_void_p))


class KeyStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.created = False
        self._key: bytes | None = None

    def load(self) -> bytes:
        if self._key is None:
            if self.path.exists():
                self._key = self._read()
            else:
                key = os.urandom(32)
                self._write(key)
                self._key, self.created = key, True
        return self._key

    def subkey(self, label: str) -> bytes:
        return hmac.new(self.load(), b"xxxtube/" + label.encode(), hashlib.sha256).digest()   # см. примечание выше

    def _write(self, key: bytes) -> None:
        if os.name == "nt":
            blob = MAGIC + bytes([M_DPAPI]) + _dpapi(key, True)
        else:                                  # разработка/тесты вне Windows
            blob = MAGIC + bytes([M_PLAIN]) + key
        atomic_write(self.path, blob, private=True)

    def _read(self) -> bytes:
        try:
            raw = self.path.read_bytes()
        except OSError as e:
            raise KeyUnavailable(f"Не удалось прочитать файл ключа: {e}") from e
        if len(raw) < 5 or raw[:3] != MAGIC:
            raise KeyUnavailable("Файл ключа повреждён")
        method, payload = raw[3], raw[4:]
        if method == M_DPAPI:
            if os.name != "nt":
                raise KeyUnavailable("Ключ создан в Windows и не читается в этой системе")
            try:
                key = _dpapi(payload, False)
            except OSError as e:
                raise KeyUnavailable("Данные созданы под другой учётной записью Windows "
                                     "или на другом компьютере") from e
        elif method == M_PLAIN:
            key = payload
        else:
            raise KeyUnavailable("Неизвестный формат ключа")
        if len(key) != 32:
            raise KeyUnavailable("Файл ключа повреждён")
        return key
