@echo off
setlocal
title ClutchCuts Studio
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
    set "PYTHON=python"
) else (
    set "PYTHON=py -3"
)

%PYTHON% -c "import flask, yt_dlp, faster_whisper" >nul 2>nul
if errorlevel 1 (
    echo Required Python packages are missing.
    echo Install them with: %PYTHON% -m pip install -r requirements.txt
    pause
    exit /b 1
)

start "" /b cmd /c "timeout /t 3 /nobreak >nul && start http://127.0.0.1:5000"
pushd "%~dp0web_app"
echo Starting ClutchCuts Studio...
%PYTHON% server.py
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" (
    echo.
    echo ClutchCuts Studio stopped with error code %EXIT_CODE%.
    pause
)
endlocal
