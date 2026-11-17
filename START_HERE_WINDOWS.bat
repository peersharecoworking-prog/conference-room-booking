@echo off
title Conference Room Booking System
cd /d "%~dp0"
echo ==========================================
echo   CONFERENCE ROOM BOOKING SYSTEM
echo ==========================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python was not found on this computer.
  echo Please install Python 3.10 or newer from https://www.python.org/downloads/
  echo During installation, tick "Add Python to PATH".
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Setting up the app for first use...
  py -m venv .venv
)
echo Installing required components...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Setup failed. Please check your internet connection and try again.
  pause
  exit /b 1
)
echo.
echo Starting your booking system...
echo Keep this black window open while using the app.
echo Open http://127.0.0.1:5000 in your browser.
echo Admin page: http://127.0.0.1:5000/admin/login
echo Default first-login password: ChangeMe123!
echo Change this password in Admin - Room Settings immediately.
echo.
".venv\Scripts\python.exe" app.py
pause
