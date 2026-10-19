from __future__ import annotations

import os
from typing import List

from PySide6.QtCore import QModelIndex, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListView, QMenu, QPushButton, QVBoxLayout,
                               QWidget)

from .icons import icon
from .library_view import CompactDelegate
from .models import ItemRole, QueueModel
from .theme import C
from .util import fmt_ms, fmt_size
from .widgets import ClickSlider, icon_button

SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]


def _speed_text(s: float) -> str:
    return (f"{s:g}").replace(".", ",") + "×"


class VideoView(QVideoWidget):
    clicked = Signal()
    doubleClicked = Signal()
    wheel = Signal(int)

    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:#000000;")
        self.setMinimumSize(320, 180)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._t = QTimer(self)
        self._t.setSingleShot(True)
        self._t.setInterval(230)
        self._t.timeout.connect(self.clicked)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._t.start()                       
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        self._t.stop()
        self.doubleClicked.emit()

    def wheelEvent(self, e):
        self.wheel.emit(1 if e.angleDelta().y() > 0 else -1)
        e.accept()


class ControlsBar(QWidget):
    prev = Signal()
    toggle = Signal()
    next_ = Signal()
    seekMoved = Signal(int)
    seekReleased = Signal(int)
    volumeChanged = Signal(int)
    muteClicked = Signal()
    speedChosen = Signal(float)
    fullscreenClicked = Signal()
    queueClicked = Signal()

    def __init__(self):
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(6, 2, 6, 4)
        v.setSpacing(0)
        self.seek = ClickSlider(thick=4, tip=lambda x: fmt_ms(x))
        self.seek.setRange(0, 0)
        self.seek.sliderMoved.connect(self._moved)
        self.seek.sliderReleased.connect(lambda: self.seekReleased.emit(self.seek.sliderPosition()))
        v.addWidget(self.seek)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.b_prev = icon_button("prev", "Предыдущее (P)", 40, 20)
        self.b_play = QPushButton()
        self.b_play.setObjectName("play")
        self.b_play.setFixedSize(44, 44)
        self.b_play.setIconSize(QSize(24, 24))
        self.b_play.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_play.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.b_next = icon_button("next", "Следующее (N)", 40, 20)
        self.time = QLabel("0:00 / 0:00")
        self.time.setObjectName("muted")
        self.time.setMinimumWidth(116)
        self.b_vol = icon_button("volume", "Звук (M)", 40, 22, track=False)
        self.vol = ClickSlider(thick=4, tip=lambda x: f"{x}%")
        self.vol.setRange(0, 100)
        self.vol.setFixedWidth(96)
        self.b_speed = QPushButton("1×")
        self.b_speed.setObjectName("ghost")
        self.b_speed.setToolTip("Скорость")
        self.b_speed.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.b_speed.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_speed.clicked.connect(self._speed_menu)
        self.b_queue = icon_button("list", "Список «Далее» (Q)", 40, 22)
        self.b_full = icon_button("full", "Во весь экран (F)", 40, 22, track=False)

        row.addWidget(self.b_prev)
        row.addWidget(self.b_play)
        row.addWidget(self.b_next)
        row.addSpacing(8)
        row.addWidget(self.time)
        row.addStretch(1)
        row.addWidget(self.b_vol)
        row.addWidget(self.vol)
        row.addSpacing(6)
        row.addWidget(self.b_speed)
        row.addWidget(self.b_queue)
        row.addWidget(self.b_full)
        v.addLayout(row)

        self.b_prev.clicked.connect(self.prev)
        self.b_play.clicked.connect(self.toggle)
        self.b_next.clicked.connect(self.next_)
        self.b_vol.clicked.connect(self.muteClicked)
        self.vol.valueChanged.connect(self.volumeChanged)
        self.b_full.clicked.connect(self.fullscreenClicked)
        self.b_queue.clicked.connect(self.queueClicked)
        self._speed = 1.0
        self._dur = 0
        self._playing, self._vol_state, self._full = False, (70, False), False
        self.set_playing(False)

    def _moved(self, v: int):
        self.time.setText(f"{fmt_ms(v)} / {fmt_ms(self._dur)}")
        self.seekMoved.emit(v)

    def _speed_menu(self):
        m = QMenu(self)
        for s in SPEEDS:
            a = m.addAction(_speed_text(s))
            a.setCheckable(True)
            a.setChecked(s == self._speed)
            a.triggered.connect(lambda _=False, s=s: self.speedChosen.emit(s))
        pos = self.b_speed.mapToGlobal(self.b_speed.rect().topLeft())
        pos.setY(pos.y() - m.sizeHint().height() - 6)
        m.exec(pos)

    def set_speed(self, s: float):
        self._speed = s
        self.b_speed.setText(_speed_text(s))

    def refresh_icons(self):
        self.set_playing(self._playing)
        self.set_volume(*self._vol_state)
        self.set_fullscreen(self._full)

    def set_playing(self, playing: bool):
        self._playing = playing
        self.b_play.setIcon(icon("pause" if playing else "play", C["on_accent"], 24))
        self.b_play.setToolTip("Пауза (Пробел)" if playing else "Воспроизвести (Пробел)")

    def set_duration(self, ms: int):
        self._dur = max(0, ms)
        self.seek.setRange(0, self._dur)
        self.time.setText(f"{fmt_ms(self.seek.value())} / {fmt_ms(self._dur)}")

    def set_position(self, ms: int):
        if not self.seek.isSliderDown():
            self.seek.setValue(ms)
            self.time.setText(f"{fmt_ms(ms)} / {fmt_ms(self._dur)}")

    def set_volume(self, v: int, muted: bool):
        self._vol_state = (v, muted)
        self.vol.blockSignals(True)
        self.vol.setValue(v)
        self.vol.blockSignals(False)
        self.b_vol.setIcon(icon("mute" if muted or v == 0 else "volume", C["text"], 22))

    def set_fullscreen(self, on: bool):
        self._full = on
        self.b_full.setIcon(icon("unfull" if on else "full", C["text"], 22))
        self.b_full.setToolTip("Выйти из полноэкранного режима (Esc)" if on else "Во весь экран (F)")

    def dragging(self) -> bool:
        return self.seek.isSliderDown() or self.vol.isSliderDown()


class PlayerPage(QWidget):
    back = Signal()
    fullscreenToggle = Signal()
    itemRequested = Signal(str)
    failed = Signal(str, str)
    volumeChanged = Signal(int, bool)
    durationKnown = Signal(str, int)
    positionSaved = Signal(str, int)
    playbackChanged = Signal(bool)

    def __init__(self, core, model):
        super().__init__()
        self.core, self.model = core, model
        self.cur = ""
        self._resume = 0
        self._muted = bool(core.settings.get("muted"))
        self._queue_on = True
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.audio = QAudioOutput(self)
        self.media = QMediaPlayer(self)
        self.media.setAudioOutput(self.audio)
        self.video = VideoView()
        self.media.setVideoOutput(self.video)

        self.bar = ControlsBar()
        self.queue = QueueModel(model, self)
        self.qview = QListView()
        self.qview.setModel(self.queue)
        self.qview.setItemDelegate(CompactDelegate(self.qview))
        self.qview.setMouseTracking(True)
        self.qview.setSelectionMode(QListView.SelectionMode.NoSelection)
        self.qview.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.qview.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.qview.setCursor(Qt.CursorShape.PointingHandCursor)
        self.qview.clicked.connect(self._queue_clicked)

        self.b_back = icon_button("back", "К библиотеке (Esc)", 40, 22)
        self.title = QLabel("")
        self.title.setObjectName("h2")
        self.sub = QLabel("")
        self.sub.setObjectName("muted")
        tcol = QVBoxLayout()
        tcol.setSpacing(0)
        tcol.addWidget(self.title)
        tcol.addWidget(self.sub)
        self.title_row = QWidget()
        tr = QHBoxLayout(self.title_row)
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(8)
        tr.addWidget(self.b_back)
        tr.addLayout(tcol, 1)

        self.left = QVBoxLayout()
        self.left.setContentsMargins(20, 12, 8, 10)
        self.left.setSpacing(8)
        self.left.addWidget(self.title_row)
        self.left.addWidget(self.video, 1)
        self.left.addWidget(self.bar)

        self.panel = QWidget()
        self.panel.setFixedWidth(372)
        pl = QVBoxLayout(self.panel)
        pl.setContentsMargins(0, 12, 8, 10)
        self.q_head = QLabel("Далее")
        self.q_head.setObjectName("h2")
        pl.addWidget(self.q_head)
        pl.addWidget(self.qview, 1)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addLayout(self.left, 1)
        root.addWidget(self.panel)

        # сигналы
        self.b_back.clicked.connect(self.back)
        self.video.clicked.connect(self.toggle_play)
        self.video.doubleClicked.connect(self.fullscreenToggle)
        self.video.wheel.connect(lambda d: self.change_volume(5 * d))
        b = self.bar
        b.toggle.connect(self.toggle_play)
        b.prev.connect(self.prev)
        b.next_.connect(self.next)
        b.fullscreenClicked.connect(self.fullscreenToggle)
        b.queueClicked.connect(self.toggle_queue)
        b.seekReleased.connect(self.media.setPosition)
        b.volumeChanged.connect(self._volume_slider)
        b.muteClicked.connect(self.toggle_mute)
        b.speedChosen.connect(self._set_speed)

        m = self.media
        m.positionChanged.connect(b.set_position)
        m.durationChanged.connect(self._on_duration)
        m.playbackStateChanged.connect(self._on_state)
        m.mediaStatusChanged.connect(self._on_status)
        m.errorOccurred.connect(self._on_error)

        vol = int(core.settings.get("volume"))
        self.audio.setVolume(vol / 100)
        self.audio.setMuted(self._muted)
        b.set_volume(vol, self._muted)

    def play_item(self, item_id: str, ids: List[str]) -> bool:
        it = self.model.item(item_id)
        if it is None:
            return False
        self.save_position()
        if not os.path.exists(it["path"]):
            self.failed.emit(it["title"], "Файл не найден: возможно, его переместили или удалили.")
            return False
        self.cur = item_id
        self.queue.set_ids(ids)
        self.queue.set_current(item_id)
        if item_id in ids:
            self.qview.scrollTo(self.queue.index(ids.index(item_id)), QListView.ScrollHint.PositionAtCenter)
        self.q_head.setText(f"Далее: {len(ids)}" if len(ids) > 1 else "Далее")
        self._resume = int(it["pos"]) if self.core.settings.get("remember_position") else 0
        self.title.setText(it["title"])
        info = [fmt_size(it["size"])] if it["size"] else []
        if it["cat"]:
            info.insert(0, it["cat"])
        self.sub.setText("   ".join(info))
        self.bar.set_duration(int(it["dur"]))
        self.bar.set_position(0)
        self.media.setSource(QUrl.fromLocalFile(it["path"]))
        self.media.play()
        return True

    def toggle_play(self):
        if self.media.source().isEmpty():
            return
        if self.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media.pause()
        else:
            self.media.play()

    def is_playing(self) -> bool:
        return self.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState

    def pause(self):
        self.media.pause()

    def stop(self):
        self.save_position()
        self.media.stop()
        self.media.setSource(QUrl())
        self.cur = ""

    def seek_rel(self, ms: int):
        d = self.media.duration()
        pos = self.media.position() + ms
        self.media.setPosition(max(0, min(pos, d if d > 0 else pos)))

    def seek_tenth(self, n: int):
        d = self.media.duration()
        if d > 0:
            self.media.setPosition(d * n // 10)

    def _step(self, delta: int):
        ids = self.queue.ids
        if self.cur in ids:
            j = ids.index(self.cur) + delta
            if 0 <= j < len(ids):
                self.itemRequested.emit(ids[j])
                return True
        return False

    def next(self):
        return self._step(1)

    def prev(self):
        if self.media.position() > 4000:
            self.media.setPosition(0)
        else:
            self._step(-1)

    def save_position(self):
        if not self.cur or not self.core.settings.get("remember_position"):
            return
        pos, dur = self.media.position(), self.media.duration()
        keep = int(pos) if pos > 5000 and dur - pos > 10000 else 0
        self.positionSaved.emit(self.cur, keep)

    def _apply_volume(self, v: int):
        v = max(0, min(100, v))
        self.audio.setVolume(v / 100)
        if v > 0 and self._muted:
            self._muted = False
            self.audio.setMuted(False)
        self.bar.set_volume(v, self._muted)
        self.volumeChanged.emit(v, self._muted)

    def _volume_slider(self, v: int):
        self._apply_volume(v)

    def change_volume(self, delta: int):
        self._apply_volume(self.bar.vol.value() + delta)

    def toggle_mute(self):
        self._muted = not self._muted
        self.audio.setMuted(self._muted)
        self.bar.set_volume(self.bar.vol.value(), self._muted)
        self.volumeChanged.emit(self.bar.vol.value(), self._muted)

    def _set_speed(self, s: float):
        self.media.setPlaybackRate(s)
        self.bar.set_speed(s)

    def _on_duration(self, d: int):
        self.bar.set_duration(d)
        it = self.model.item(self.cur) if self.cur else None
        if it and d > 0 and abs(it["dur"] - d) > 1000:
            it["dur"] = int(d)
            self.durationKnown.emit(self.cur, int(d))

    def _on_state(self, st):
        playing = st == QMediaPlayer.PlaybackState.PlayingState
        self.bar.set_playing(playing)
        self.playbackChanged.emit(playing)

    def _on_status(self, st):
        S = QMediaPlayer.MediaStatus
        if st == S.LoadedMedia and self._resume > 0:
            self.media.setPosition(self._resume)
            self._resume = 0
        elif st == S.EndOfMedia:
            if self.core.settings.get("autoplay_next"):
                self.next()

    def _on_error(self, error, message=""):
        it = self.model.item(self.cur) if self.cur else None
        name = it["title"] if it else "видео"
        self.failed.emit(name, "Не удалось воспроизвести: формат или кодек не поддерживается, либо файл повреждён.")

    def _queue_clicked(self, idx: QModelIndex):
        item = idx.data(ItemRole)
        if item:
            self.itemRequested.emit(item["id"])

    def toggle_queue(self):
        self._queue_on = not self._queue_on
        self.panel.setVisible(self._queue_on)

    def enter_fullscreen(self, host):
        self.left.removeWidget(self.bar)
        host.attach(self.bar)
        self.bar.set_fullscreen(True)
        self.title_row.hide()
        self.panel.hide()
        self.left.setContentsMargins(0, 0, 0, 0)

    def exit_fullscreen(self, host):
        host.detach(self.bar)
        self.left.addWidget(self.bar)
        self.bar.show()
        self.bar.set_fullscreen(False)
        self.title_row.show()
        self.panel.setVisible(self._queue_on)
        self.left.setContentsMargins(20, 12, 8, 10)
        self.set_cursor_hidden(False)

    def set_cursor_hidden(self, hide: bool):
        self.video.setCursor(Qt.CursorShape.BlankCursor if hide else Qt.CursorShape.ArrowCursor)
