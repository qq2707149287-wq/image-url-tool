@echo off
chcp 65001 >nul
title Image URL Tool Launcher

echo ===================================================
echo      Image URL Tool - One Click Start
echo ===================================================

echo.
echo [1/3] Checking environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    pause
    exit /b
)

echo.
echo [2/3] Installing dependencies (if needed)...
pip install -r requirements.txt >nul 2>&1
if %errorlevel% neq 0 (
    echo Warning: Failed to install requirements. Trying to proceed...
)

echo.
echo [3/3] Starting server...
echo.
echo    Server will start at: http://localhost:8000
echo    Please keep this window open.
echo.

start http://localhost:8000
python run.py

pause
