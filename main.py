"""SecureTube — точка входа."""
from __future__ import annotations

import getpass
import sys
import traceback


def _make_shortcut_cli() -> int:
    from securetube.shortcuts import create_shortcuts
    ok, _msg = create_shortcuts()
    return 0 if ok else 1


def main(argv: list) -> int:
    if "--make-shortcut" in argv:               # вызывается установщиком, без окна
        return _make_shortcut_cli()

    import os
    from PySide6.QtCore import QCoreApplication, Qt
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtNetwork import QLocalServer, QLocalSocket
    from PySide6.QtWidgets import QApplication

    from securetube import APP_ID, APP_NAME, winutil
    from securetube.core import Core, KeyUnavailable, reset_keys
    from securetube.dialogs import DarkMessageBox, LoginDialog, confirm, notify
    from securetube.icons import app_icon
    from securetube import theme
    from securetube.theme import build_qss, font, pick_family
    from securetube.vault import VaultError

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    # Chromium для раздела «Сайты»: утечки локального IP через WebRTC и фоновые обращения в сеть выключены.
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS",
                          "--force-webrtc-ip-handling-policy=disable_non_proxied_udp --disable-background-networking")
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    try:                                         # импортируется до QApplication (требование Qt); если компонента нет, раздел «Сайты» подскажет
        from PySide6 import QtWebEngineWidgets  # noqa: F401
    except Exception:
        pass
    winutil.set_app_id(APP_ID)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)         # окно прячется на время ввода пароля
    app.setStyle("Fusion")
    pick_family()
    app.setFont(font(14))
    app.setStyleSheet(build_qss())
    app.setWindowIcon(app_icon())

    def on_error(exc_type, exc, tb):
        if sys.stderr:                           # в оконной сборке stderr отсутствует
            traceback.print_exception(exc_type, exc, tb)
        try:
            box = DarkMessageBox()
            box.setWindowTitle(APP_NAME)
            box.setText("<b>Что-то пошло не так</b>")
            box.setInformativeText(f"{exc_type.__name__}: {exc}\n\nДанные не потеряны. Если ошибка повторяется, "
                                   "перезапустите программу.")
            box.exec()
        except Exception:
            pass
    sys.excepthook = on_error

    # --- один экземпляр: повторный запуск просто поднимает окно
    name = f"securetube-{getpass.getuser()}"
    sock = QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(300):
        sock.write(b"show")
        sock.flush()
        sock.waitForBytesWritten(300)
        return 0
    QLocalServer.removeServer(name)
    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    server.listen(name)

    # --- данные и ключ
    try:
        core = Core()
    except KeyUnavailable as e:
        if not confirm(None, "Не удаётся открыть данные",
                       f"{e}.\n\nМожно начать заново: библиотека и настройки будут созданы с нуля, "
                       "пароль вернётся к стартовому. Видео в папке хранения останутся на диске.",
                       ok="Начать заново", cancel="Выйти"):
            return 1
        reset_keys()
        core = Core()
    except VaultError as e:
        notify(None, "Не хватает компонента", str(e))
        return 1
    except OSError as e:
        notify(None, "Нет доступа к данным", f"Не удалось подготовить папку данных: {e.strerror or e}")
        return 1
    statuses = core.load()
    core.ext.scan()
    theme.apply(core.ext.theme(str(core.settings.get("theme"))), core.ext.accent(str(core.settings.get("accent"))))

    if LoginDialog(core.auth).exec() != LoginDialog.DialogCode.Accepted:
        return 0

    from securetube.main_window import MainWindow
    win = MainWindow(core)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), win.bring_to_front()))
    win.show()
    win.report_status(statuses)
    win.startup_tasks()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
