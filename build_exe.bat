@echo off
chcp 65001 >nul
cd /d "%~dp0"
REM  build_exe.bat           - быстрый запуск (папка), рекомендуется
REM  build_exe.bat onefile   - один файл SecureTube.exe (стартует медленнее)
set MODE=--onedir
if /i "%~1"=="onefile" set MODE=--onefile
if not exist .venv\Scripts\python.exe call install.bat
if errorlevel 1 exit /b 1
echo === Сборка SecureTube ===
echo Внимание: встроенный браузер Chromium делает папку программы крупнее, около 300 МБ. Это нормально.
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
.venv\Scripts\python -m PyInstaller --noconfirm --clean --windowed %MODE% --name SecureTube --icon assets\securetube.ico --add-data "assets\securetube.ico;assets" --add-data "extensions;extensions" --exclude-module tkinter --exclude-module unittest main.py
if errorlevel 1 goto fail
echo.
echo === Установка и ярлыки ===
call install_app.bat
if errorlevel 1 goto fail
exit /b 0
:fail
echo Сборка не удалась. Текст ошибки выше.
pause
exit /b 1
