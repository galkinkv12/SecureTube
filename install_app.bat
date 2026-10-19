@echo off
chcp 65001 >nul
cd /d "%~dp0"
set DEST=%LOCALAPPDATA%\Programs\SecureTube
set SRC_DIR=dist\SecureTube\SecureTube.exe
set SRC_ONE=dist\SecureTube.exe
if not exist "%SRC_DIR%" if not exist "%SRC_ONE%" goto nobuild
taskkill /im SecureTube.exe /f >nul 2>nul
taskkill /im XXXtube.exe /f >nul 2>nul
if exist "%LOCALAPPDATA%\Programs\XXXtube" attrib -h -s "%LOCALAPPDATA%\Programs\XXXtube\_internal" >nul 2>nul
if exist "%LOCALAPPDATA%\Programs\XXXtube" rmdir /s /q "%LOCALAPPDATA%\Programs\XXXtube"
if exist "%DEST%" attrib -h -s "%DEST%\_internal" >nul 2>nul
if exist "%DEST%" rmdir /s /q "%DEST%"
mkdir "%DEST%"
if exist "%SRC_DIR%" xcopy /e /i /y /q "dist\SecureTube\*" "%DEST%\" >nul
if not exist "%SRC_DIR%" copy /y "%SRC_ONE%" "%DEST%\SecureTube.exe" >nul
attrib +h +s "%DEST%\_internal" >nul 2>nul
start "" /wait "%DEST%\SecureTube.exe" --make-shortcut
if errorlevel 1 goto noshortcut
echo Готово: программа в "%DEST%", ярлык на рабочем столе и в меню Пуск.
echo Ваши видео и настройки лежат отдельно: %LOCALAPPDATA%\SecureTube (скрытая папка), обновление их не трогает.
echo Если раньше стоял XXXtube, его данные перенесутся автоматически при первом запуске.
exit /b 0
:nobuild
echo Сначала соберите программу: build_exe.bat
exit /b 1
:noshortcut
echo Программа установлена, но ярлык создать не удалось. Создайте его в программе: Настройки - Ярлык на рабочем столе.
exit /b 0
