@echo off
setlocal enabledelayedexpansion

echo ==================================================
echo  Stopping NOC Automation (Backend ^& Frontend)
echo ==================================================

echo Freeing port 8000 (Backend)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo Freeing port 5173 (Frontend)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1
)

echo Stopping any leftover uvicorn or vite windows...
taskkill /F /FI "WINDOWTITLE eq NOC Backend*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq NOC Frontend*" >nul 2>&1

echo ==================================================
echo  All NOC servers have been stopped.
echo ==================================================
timeout /t 3 >nul 2>&1
