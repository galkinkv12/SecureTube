from __future__ import annotations

import os

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception as _e:  # pragma: no cover
    AESGCM = None
    InvalidTag = Exception
    _IMPORT_ERROR = _e
else:
    _IMPORT_ERROR = None

MAGIC = b"XT\x01"


class VaultError(Exception):
    pass


class Vault:
    def __init__(self, key: bytes):
        if AESGCM is None:
            raise VaultError(f"Не установлена библиотека cryptography: {_IMPORT_ERROR}")
        if len(key) != 32:
            raise VaultError("Неверная длина ключа")
        self._aes = AESGCM(key)

    def seal(self, data: bytes, label: str) -> bytes:
        nonce = os.urandom(12)
        return MAGIC + nonce + self._aes.encrypt(nonce, data, label.encode())

    def open(self, blob: bytes, label: str) -> bytes:
        if len(blob) < len(MAGIC) + 12 + 16 or blob[:3] != MAGIC:
            raise VaultError("Файл повреждён или имеет неизвестный формат")
        nonce, ct = blob[3:15], blob[15:]
        try:
            return self._aes.decrypt(nonce, ct, label.encode())
        except InvalidTag as e:
            raise VaultError("Файл изменён или создан другим ключом") from e
