from __future__ import annotations

import os
from pathlib import Path
from typing import List

from PySide6.QtCore import QThread, Signal

from . import importer


class ImportWorker(QThread):
    progress = Signal(int, int, str, float)     # номер, всего, имя, доля текущего файла
    imported = Signal(object)                   # новый элемент библиотеки (dict)
    skipped = Signal(str)                       # уже в библиотеке
    failed = Signal(str, str)                   # имя, причина

    def __init__(self, files: List[Path], known: set, mode: str, media_dir: Path,
                 delete_original: bool, parent=None):
        super().__init__(parent)
        self.files, self.known, self.mode = files, known, mode
        self.media_dir, self.delete_original = media_dir, delete_original
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        total = len(self.files)
        for n, src in enumerate(self.files, 1):
            if self._cancel:
                break
            name = src.name
            self.progress.emit(n, total, name, 0.0)
            try:
                item = importer.import_one(
                    src, self.known, self.mode, self.media_dir, self.delete_original,
                    lambda f, n=n, name=name: self.progress.emit(n, total, name, f),
                    lambda: self._cancel)
            except importer.Cancelled:
                break
            except importer.ImportFailed as e:
                self.failed.emit(name, str(e))
                continue
            except Exception as e:                       
                self.failed.emit(name, f"Неожиданная ошибка: {e}")
                continue
            if item is None:
                self.skipped.emit(name)
            else:
                self.imported.emit(item)


class MissingChecker(QThread):
    result = Signal(object)                     

    def __init__(self, pairs: List[tuple], parent=None):
        super().__init__(parent)
        self.pairs = pairs

    def run(self) -> None:
        self.result.emit({iid for iid, path in self.pairs if not os.path.exists(path)})
