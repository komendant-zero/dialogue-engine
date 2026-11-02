@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

set "PYTHON_CMD="
if exist "D:\python312\python.exe" (
    set "PYTHON_CMD=D:\python312\python.exe"
) else (
    set "PYTHON_CMD=python"
)

%PYTHON_CMD% "%~dp0mcp_server.py" %*
