from __future__ import annotations

import os


def set_app_id(app_id: str) -> None:
    """Чтобы значок в панели задач был свой, а не питоновский."""
    if os.name != "nt":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except Exception:
        pass


def _dwm(hwnd: int, attr: int, value: int) -> bool:
    import ctypes
    from ctypes import wintypes
    fn = ctypes.windll.dwmapi.DwmSetWindowAttribute
    fn.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    fn.restype = ctypes.c_long
    v = ctypes.c_int(value)
    return fn(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v)) == 0


def dark_titlebar(hwnd: int, caption_hex: str = "#13151B", text_hex: str = "#EDEFF4", dark: bool = True) -> None:
    """Заголовок окна в цвет темы (Windows 10 2004+ / Windows 11)."""
    if os.name != "nt":
        return

    def bgr(h: str) -> int:
        h = h.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return r | (g << 8) | (b << 16)
    try:
        if not _dwm(hwnd, 20, 1 if dark else 0):
            _dwm(hwnd, 19, 1 if dark else 0)
        _dwm(hwnd, 35, bgr(caption_hex))      # цвет заголовка (Windows 11)
        _dwm(hwnd, 36, bgr(text_hex))
    except Exception:
        pass


def capture_hidden(hwnd: int, hide: bool) -> None:
    """Окно не попадает в скриншоты и демонстрацию экрана (Windows 10 2004+)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes
        fn = ctypes.windll.user32.SetWindowDisplayAffinity
        fn.argtypes = [wintypes.HWND, wintypes.DWORD]
        fn(hwnd, 0x11 if hide else 0x0)
    except Exception:
        pass
