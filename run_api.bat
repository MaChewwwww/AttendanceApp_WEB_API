@echo off
cd /d "%~dp0"
title AttendanceApp API Server
color 0A
echo.
echo ==========================================
echo    AttendanceApp API Server Launcher
echo ==========================================
echo.
echo Starting API server...
echo.
python run_api.py
echo.
echo ==========================================
echo    API Server has stopped
echo ==========================================
echo.
pause
