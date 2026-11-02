@echo off
chcp 65001 > nul
title Dialogue Engine - Dependencies Installer

echo ===================================================
echo   Dialogue Engine - Installing Dependencies
echo ===================================================

set "PYTHON_CMD="
if exist "D:\python312\python.exe" (
    set "PYTHON_CMD=D:\python312\python.exe"
) else (
    set "PYTHON_CMD=python"
)

echo [OK] Python: %PYTHON_CMD%
cd /d "%~dp0"

echo.
echo Installing packages from requirements.txt...
%PYTHON_CMD% -m pip install -r requirements.txt

echo.
echo ===================================================
echo Testing installed packages:
%PYTHON_CMD% -c "import PIL, fastapi, uvicorn, qrcode, websocket; print('All dependencies successfully installed and verified!')"
echo ===================================================
echo.
pause
