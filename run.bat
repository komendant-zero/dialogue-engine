@echo off
chcp 65001 > nul
title Dialogue Engine

echo ===================================================
echo   Dialogue Engine - Starting Editor...
echo ===================================================

set "PYTHON_CMD="
if exist "D:\python312\python.exe" (
    set "PYTHON_CMD=D:\python312\python.exe"
) else (
    set "PYTHON_CMD=python"
)

echo [OK] Python: %PYTHON_CMD%
cd /d "%~dp0"

%PYTHON_CMD% main.py %*

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application exited with code: %errorlevel%
    pause
)
