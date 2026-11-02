@echo off
chcp 65001 > nul
title Dialogue Engine - Cowork Server 24/7

echo ===================================================
echo   Dialogue Engine - Cowork Server 24/7
echo ===================================================

set "PYTHON_CMD="
if exist "D:\python312\python.exe" (
    set "PYTHON_CMD=D:\python312\python.exe"
) else (
    set "PYTHON_CMD=python"
)

cd /d "%~dp0"
%PYTHON_CMD% server.py --host 0.0.0.0 --port 8000 --project violant.json
if %errorlevel% neq 0 (
    echo.
    echo Server exited with code: %errorlevel%
    pause
)
