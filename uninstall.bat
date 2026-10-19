@echo off
chcp 65001 >nul
set DEST=%LOCALAPPDATA%\Programs\SecureTube
taskkill /im SecureTube.exe /f >nul 2>nul
taskkill /im XXXtube.exe /f >nul 2>nul
if exist "%LOCALAPPDATA%\Programs\XXXtube" attrib -h -s "%LOCALAPPDATA%\Programs\XXXtube\_internal" >nul 2>nul
if exist "%LOCALAPPDATA%\Programs\XXXtube" rmdir /s /q "%LOCALAPPDATA%\Programs\XXXtube"
del /q "%USERPROFILE%\Desktop\XXXtube.lnk" >nul 2>nul
del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\XXXtube.lnk" >nul 2>nul
if exist "%DEST%" attrib -h -s "%DEST%\_internal" >nul 2>nul
if exist "%DEST%" rmdir /s /q "%DEST%"
del /q "%USERPROFILE%\Desktop\SecureTube.lnk" >nul 2>nul
del /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\SecureTube.lnk" >nul 2>nul
echo Программа и ярлыки удалены. Видео и настройки сохранены в %LOCALAPPDATA%\SecureTube.
echo Чтобы удалить и их, удалите эту папку вручную (она скрытая).
pause
