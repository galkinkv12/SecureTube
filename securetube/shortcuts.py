from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple

from . import APP_NAME, paths


def launch_target() -> Tuple[str, str, str, str]:
    """(программа, аргументы, рабочая папка, значок)"""
    if paths.is_frozen():
        exe = sys.executable
        return exe, "", str(paths.app_dir()), f"{exe},0"
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = str(pyw if pyw.exists() else sys.executable)
    main = paths.app_dir() / "main.py"
    return exe, f'"{main}"', str(paths.app_dir()), str(paths.resource("assets", "securetube.ico"))


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def build_script(desktop: bool = True, start_menu: bool = True) -> str:
    exe, args, cwd, icon = launch_target()
    lines = [
        "$ErrorActionPreference = 'Stop'",
        "$w = New-Object -ComObject WScript.Shell",
        "function Make($dir) {",
        "  if (-not $dir) { return }",
        f"  $lnk = Join-Path $dir {_q(APP_NAME + '.lnk')}",
        "  $s = $w.CreateShortcut($lnk)",
        f"  $s.TargetPath = {_q(exe)}",
        f"  $s.Arguments = {_q(args)}",
        f"  $s.WorkingDirectory = {_q(cwd)}",
        f"  $s.IconLocation = {_q(icon)}",
        f"  $s.Description = {_q(APP_NAME)}",
        "  $s.Save()",
        "  Write-Output $lnk",
        "}",
    ]
    # ярлыки прежнего названия убираем, чтобы не было дублей
    lines += ["function Legacy($dir) {",
              "  if (-not $dir) { return }",
              "  Remove-Item -LiteralPath (Join-Path $dir 'XXXtube.lnk') -ErrorAction SilentlyContinue",
              "}"]
    if desktop:
        lines.append("Legacy ([Environment]::GetFolderPath('Desktop'))")
        lines.append("Make ([Environment]::GetFolderPath('Desktop'))")
    if start_menu:
        lines.append("Legacy ([Environment]::GetFolderPath('Programs'))")
        lines.append("Make ([Environment]::GetFolderPath('Programs'))")
    return "\n".join(lines)


def create_shortcuts(desktop: bool = True, start_menu: bool = True) -> Tuple[bool, str]:
    if os.name != "nt":
        return False, "Ярлыки создаются только в Windows"
    enc = base64.b64encode(build_script(desktop, start_menu).encode("utf-16-le")).decode()
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-EncodedCommand", enc],
            capture_output=True, text=True, timeout=40, creationflags=0x08000000)
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"Не удалось запустить PowerShell: {e}"
    if r.returncode != 0:
        return False, "Не удалось создать ярлык. Проверьте права на запись в рабочий стол."
    return True, "Ярлык SecureTube создан на рабочем столе"
