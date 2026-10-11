@echo off
setlocal enabledelayedexpansion

echo ==================================================
echo  Starting NOC Automation (Backend ^& Frontend)
echo ==================================================

set "REPO_ROOT=%~dp0"
set "BACKEND_DIR=%REPO_ROOT%backend"
set "FRONTEND_DIR=%REPO_ROOT%frontend"
set "VENV_DIR=%BACKEND_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"

:: -----------------------------------------------------------------------------
:: 1. Check & Setup Python Virtual Environment (Backend)
:: -----------------------------------------------------------------------------
echo.
echo [1/4] Checking Python environment...
where python >nul 2>&1
if %errorlevel% neq 0 (
    where py >nul 2>&1
    if %errorlevel% neq 0 (
        echo ERROR: Python is not installed or not in PATH.
        echo Please install Python 3.9+ from https://www.python.org/
        pause
        exit /b 1
    )
    set "SYSTEM_PYTHON=py -3"
) else (
    set "SYSTEM_PYTHON=python"
)

:: Create venv if not present
if not exist "%VENV_PYTHON%" (
    echo   -^> Virtual environment not found at backend\.venv. Creating...
    %SYSTEM_PYTHON% -m venv "%VENV_DIR%"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment at "%VENV_DIR%".
        pause
        exit /b 1
    )
    echo   -^> Virtual environment created successfully.
)

:: Check if required packages are installed
echo [2/4] Checking backend dependencies...
"%VENV_PYTHON%" -c "import fastapi, uvicorn, aiosqlite, pydantic, pydantic_settings" >nul 2>&1
if %errorlevel% neq 0 (
    echo   -^> Required packages missing. Installing from backend\requirements.txt...
    "%VENV_PIP%" install --upgrade pip
    "%VENV_PIP%" install -r "%BACKEND_DIR%\requirements.txt"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install backend dependencies.
        pause
        exit /b 1
    )
    echo   -^> Backend dependencies installed successfully.
) else (
    echo   -^> Backend dependencies already installed.
)

:: -----------------------------------------------------------------------------
:: 2. Check & Setup Node Modules (Frontend)
:: -----------------------------------------------------------------------------
echo.
echo [3/4] Checking Node.js and frontend dependencies...
where npm >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: 'npm' was not found in PATH.
    echo Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)

if not exist "%FRONTEND_DIR%\node_modules" (
    echo   -^> node_modules not found in frontend\. Running 'npm install'...
    pushd "%FRONTEND_DIR%"
    call npm install
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install frontend dependencies.
        popd
        pause
        exit /b 1
    )
    popd
    echo   -^> Frontend dependencies installed successfully.
) else (
    echo   -^> Frontend node_modules already present.
)

:: -----------------------------------------------------------------------------
:: 3. Launch Backend and Frontend
:: -----------------------------------------------------------------------------
echo.
echo [4/4] Launching Backend and Frontend...
echo   -^> Backend:  http://localhost:8000 (API ^& Docs at /docs)
echo   -^> Frontend: http://localhost:5173
echo ==================================================
echo.

start "NOC Backend" cmd /k "cd /d "%BACKEND_DIR%" && "%VENV_PYTHON%" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
start "NOC Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

echo Both servers launched in separate terminal windows.
echo Close those windows or press Ctrl+C in them to stop the servers.
