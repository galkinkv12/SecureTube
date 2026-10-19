from __future__ import annotations

from collections import deque
from typing import Deque, Optional, Tuple

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QMediaPlayer, QVideoSink

TW, TH = 320, 180
GUARD_MS = 10000      
SETTLE_MS = 650       


class Thumbnailer(QObject):
    """Последовательно открывает файлы, снимает кадр с ~10% и узнаёт длительность.

    done(item_id, jpeg_bytes | None, duration_ms). Если кадр взять не удалось,
    jpeg_bytes = None, а карточка получит аккуратную заглушку.
    """
    done = Signal(str, object, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._queue: Deque[Tuple[str, str]] = deque()
        self._job: Optional[Tuple[str, str]] = None
        self._phase = "idle"
        self._image: Optional[QImage] = None
        self._duration = 0
        self._ready = False

        self._player = QMediaPlayer(self)
        self._sink = QVideoSink(self)
        self._player.setVideoSink(self._sink)
        self._player.mediaStatusChanged.connect(self._on_status)
        self._player.errorOccurred.connect(self._on_error)
        self._player.durationChanged.connect(self._on_duration)
        self._sink.videoFrameChanged.connect(self._on_frame)

        self._guard = QTimer(self)
        self._guard.setSingleShot(True)
        self._guard.setInterval(GUARD_MS)
        self._guard.timeout.connect(self._finish)
        self._settle = QTimer(self)
        self._settle.setSingleShot(True)
        self._settle.setInterval(SETTLE_MS)
        self._settle.timeout.connect(self._on_settled)

    def pending(self) -> int:
        return len(self._queue) + (1 if self._job else 0)

    def enqueue(self, item_id: str, path: str) -> None:
        if (self._job and self._job[0] == item_id) or any(j[0] == item_id for j in self._queue):
            return
        self._queue.append((item_id, path))
        self._next()

    def cancel(self, item_id: str) -> None:
        self._queue = deque(j for j in self._queue if j[0] != item_id)

    def _next(self) -> None:
        if self._job or not self._queue:
            return
        self._job = self._queue.popleft()
        self._phase, self._image, self._duration, self._ready = "load", None, 0, False
        self._guard.start()
        self._player.setSource(QUrl.fromLocalFile(self._job[1]))

    # --- события плеера
    def _on_status(self, status) -> None:
        if not self._job:
            return
        S = QMediaPlayer.MediaStatus
        if status in (S.LoadedMedia, S.BufferedMedia) and self._phase == "load":
            self._phase = "grab"
            d = self._player.duration()
            self._duration = max(self._duration, d)
            target = 0 if d <= 0 else min(max(int(d * 0.10), 800), max(d - 1000, 0))
            if target > 0:
                self._player.setPosition(target)
            self._player.play()
            self._settle.start()
        elif status == S.InvalidMedia:
            self._finish()

    def _on_error(self, *_args) -> None:
        if self._job:
            self._finish()

    def _on_duration(self, d: int) -> None:
        if self._job and d > 0:
            self._duration = d

    def _on_frame(self, frame) -> None:
        if not self._job or self._phase != "grab" or not frame.isValid():
            return
        img = frame.toImage()
        if img.isNull():
            return
        self._image = img
        if self._ready:
            self._finish()

    def _on_settled(self) -> None:
        self._ready = True
        if self._image is not None:
            self._finish()

    # --- завершение
    @staticmethod
    def _encode(img: QImage) -> Optional[bytes]:
        s = img.convertToFormat(QImage.Format.Format_RGB32).scaled(
            TW, TH, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        s = s.copy((s.width() - TW) // 2, (s.height() - TH) // 2, TW, TH)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        ok = s.save(buf, "JPG", 85)
        buf.close()
        return bytes(ba.data()) if ok else None

    def _finish(self) -> None:
        if not self._job:
            return
        item_id, _ = self._job
        self._job = None
        self._phase = "idle"
        self._guard.stop()
        self._settle.stop()
        jpeg = self._encode(self._image) if self._image is not None else None
        dur = self._duration
        self._image = None
        self._player.stop()
        self._player.setSource(QUrl())
        self.done.emit(item_id, jpeg, dur)
        QTimer.singleShot(120, self._next)
