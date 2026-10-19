from __future__ import annotations

from PySide6.QtCore import QPoint, QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
                               QVBoxLayout)

from . import theme
from .auth import MIN_PASSWORD
from .icons import logo_pixmap
from .util import fmt_ban


class DarkMessageBox(QMessageBox):
    def showEvent(self, e):
        super().showEvent(e)
        theme.decorate(int(self.winId()))


class DarkDialog(QDialog):
    def showEvent(self, e):
        super().showEvent(e)
        theme.decorate(int(self.winId()))


def confirm(parent, title: str, text: str, ok: str = "Удалить", cancel: str = "Отмена") -> bool:
    box = DarkMessageBox(parent)
    box.setWindowTitle("SecureTube")
    box.setIcon(QMessageBox.Icon.NoIcon)
    box.setText(f"<b>{title}</b>")
    box.setInformativeText(text)
    okb = box.addButton(ok, QMessageBox.ButtonRole.AcceptRole)
    cb = box.addButton(cancel, QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cb)
    box.exec()
    return box.clickedButton() is okb


def notify(parent, title: str, text: str) -> None:
    box = DarkMessageBox(parent)
    box.setWindowTitle("SecureTube")
    box.setIcon(QMessageBox.Icon.NoIcon)
    box.setText(f"<b>{title}</b>")
    box.setInformativeText(text)
    box.addButton("Понятно", QMessageBox.ButtonRole.AcceptRole)
    box.exec()


def choose(parent, title: str, text: str, yes: str, no: str) -> bool:
    return confirm(parent, title, text, ok=yes, cancel=no)


class LoginDialog(DarkDialog):
    def __init__(self, auth):
        super().__init__()
        self.auth = auth
        self.setWindowTitle("SecureTube")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setFixedWidth(380)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 34, 36, 30)
        lay.setSpacing(10)
        mark = QLabel()
        mark.setPixmap(logo_pixmap(64))
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        word = QLabel('<span style="font-weight:800;">Secure</span><span style="font-weight:400;">Tube</span>')
        word.setStyleSheet("font-size:28px;")
        word.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel("Введите пароль")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText("Пароль")
        self.edit.returnPressed.connect(self.try_login)
        self.btn = QPushButton("Войти")
        self.btn.setObjectName("primary")
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.clicked.connect(self.try_login)
        self.msg = QLabel("")
        self.msg.setObjectName("error")
        self.msg.setWordWrap(True)
        self.msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.msg.setMinimumHeight(40)
        for w in (mark, word, hint):
            lay.addWidget(w)
        lay.addSpacing(8)
        lay.addWidget(self.edit)
        lay.addWidget(self.btn)
        lay.addWidget(self.msg)
        self._shake = QPropertyAnimation(self, b"pos", self)
        left = auth.ban_remaining()
        if left:
            self.block(left)
        self.edit.setFocus()

    def block(self, sec: int):
        self.edit.setDisabled(True)
        self.btn.setDisabled(True)
        self.msg.setText(f"Доступ заблокирован.\nОсталось: {fmt_ban(sec)}")
        QTimer.singleShot(3500, self.reject)

    def _do_shake(self):
        p = self.pos()
        self._shake.stop()
        self._shake.setDuration(340)
        self._shake.setKeyValueAt(0.0, p)
        for t, dx in ((0.2, -12), (0.4, 12), (0.6, -8), (0.8, 8)):
            self._shake.setKeyValueAt(t, p + QPoint(dx, 0))
        self._shake.setKeyValueAt(1.0, p)
        self._shake.start()

    def try_login(self):
        res, val = self.auth.attempt(self.edit.text())
        self.edit.clear()
        if res == "ok":
            self.accept()
        elif res == "wrong":
            self.msg.setText(f"Неверный пароль. Осталось попыток: {val}")
            self._do_shake()
            self.edit.setDisabled(True)           
            self.btn.setDisabled(True)
            QTimer.singleShot(1200, self._unfreeze)
        else:
            self.block(val)

    def _unfreeze(self):
        self.edit.setDisabled(False)
        self.btn.setDisabled(False)
        self.edit.setFocus()


class ChangePasswordDialog(DarkDialog):
    def __init__(self, auth, parent=None):
        super().__init__(parent)
        self.auth = auth
        self.setWindowTitle("Смена пароля")
        self.setFixedWidth(400)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 26, 28, 24)
        lay.setSpacing(10)
        title = QLabel("Смена пароля")
        title.setObjectName("h2")
        lay.addWidget(title)
        self.old = self._field("Текущий пароль")
        self.new = self._field(f"Новый пароль (не короче {MIN_PASSWORD} символов)")
        self.rep = self._field("Повторите новый пароль")
        for e in (self.old, self.new, self.rep):
            lay.addWidget(e)
        self.msg = QLabel("")
        self.msg.setObjectName("error")
        self.msg.setWordWrap(True)
        self.msg.setMinimumHeight(36)
        lay.addWidget(self.msg)
        row = QHBoxLayout()
        row.addStretch(1)
        cancel = QPushButton("Отмена")
        cancel.clicked.connect(self.reject)
        self.ok = QPushButton("Сменить пароль")
        self.ok.setObjectName("primary")
        self.ok.clicked.connect(self._submit)
        row.addWidget(cancel)
        row.addWidget(self.ok)
        lay.addLayout(row)

    @staticmethod
    def _field(ph: str) -> QLineEdit:
        e = QLineEdit()
        e.setEchoMode(QLineEdit.EchoMode.Password)
        e.setPlaceholderText(ph)
        return e

    def _submit(self):
        if self.new.text() != self.rep.text():
            self.msg.setText("Новые пароли не совпадают.")
            return
        res = self.auth.set_password(self.old.text(), self.new.text())
        if res == "ok":
            self.accept()
        elif res == "short":
            self.msg.setText(f"Новый пароль слишком короткий: нужно не меньше {MIN_PASSWORD} символов.")
        elif res == "wrong":
            self.msg.setText("Текущий пароль неверный. Неверные попытки считаются так же, как при входе.")
        else:
            self.msg.setText("Слишком много неверных попыток — смена пароля заблокирована.")


def prompt(parent, title: str, label: str, text: str = "", ok: str = "Готово"):
    dlg = DarkDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setFixedWidth(400)
    lay = QVBoxLayout(dlg)
    lay.setContentsMargins(28, 26, 28, 24)
    lay.setSpacing(10)
    t = QLabel(label)
    t.setObjectName("h2")
    edit = QLineEdit(text)
    edit.setMaxLength(120)
    edit.selectAll()
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = QPushButton("Отмена")
    cancel.clicked.connect(dlg.reject)
    okb = QPushButton(ok)
    okb.setObjectName("primary")
    okb.clicked.connect(dlg.accept)
    edit.returnPressed.connect(dlg.accept)
    row.addWidget(cancel)
    row.addWidget(okb)
    lay.addWidget(t)
    lay.addWidget(edit)
    lay.addSpacing(6)
    lay.addLayout(row)
    edit.setFocus()
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return None
    value = " ".join(edit.text().split())
    return value or None
