@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === SecureTube: подготовка окружения ===
set PY=
where py >nul 2>nul && set PY=py -3
if not defined PY where python >nul 2>nul && set PY=python
if not defined PY goto nopython
if not exist .venv\Scripts\python.exe %PY% -m venv .venv
if errorlevel 1 goto fail
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements-build.txt
if errorlevel 1 goto fail
echo.
echo Готово. Запуск без сборки: run.bat   Сборка EXE: build_exe.bat
exit /b 0
:nopython
echo Python 3.9-3.12 не найден. Установите его с python.org и отметьте галочку Add Python to PATH.
pause
exit /b 1
:fail
echo Не удалось подготовить окружение. Проверьте интернет-соединение: оно нужно только для установки.
pause
exit /b 1
