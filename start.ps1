<#
.SYNOPSIS
    Starts NOC Automation backend and frontend on Windows (PowerShell).
.DESCRIPTION
    Checks for Python virtual environment in backend/.venv, creates it and installs
    requirements from backend/requirements.txt if missing.
    Checks for node_modules in frontend/, installs with npm install if missing.
    Launches both backend and frontend servers in separate processes.
#>

$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$VenvDir = Join-Path $BackendDir ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Starting NOC Automation (Backend & Frontend)" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# ------------------------------------------------------------------------------
# 1. Check & Setup Python Virtual Environment (Backend)
# ------------------------------------------------------------------------------
Write-Host "`n[1/4] Checking Python environment..." -ForegroundColor Yellow
$SystemPython = $null
if (Get-Command python -ErrorAction SilentlyContinue) {
    $SystemPython = "python"
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $SystemPython = "py"
} else {
    Write-Error "Python is not installed or not in PATH. Please install Python 3.9+ from https://www.python.org/"
    exit 1
}

# Create venv if not present
if (-not (Test-Path $VenvPython)) {
    Write-Host "  -> Virtual environment not found at backend\.venv. Creating..." -ForegroundColor Gray
    & $SystemPython -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to create virtual environment."
        exit 1
    }
    Write-Host "  -> Virtual environment created successfully." -ForegroundColor Green
}

# Check requirements
Write-Host "[2/4] Checking backend dependencies..." -ForegroundColor Yellow
& $VenvPython -c "import fastapi, uvicorn, aiosqlite, pydantic, pydantic_settings" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  -> Required packages missing. Installing from backend\requirements.txt..." -ForegroundColor Gray
    & $VenvPip install --upgrade pip
    & $VenvPip install -r (Join-Path $BackendDir "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install backend requirements."
        exit 1
    }
    Write-Host "  -> Backend dependencies installed successfully." -ForegroundColor Green
} else {
    Write-Host "  -> Backend dependencies already installed." -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 2. Check & Setup Node Modules (Frontend)
# ------------------------------------------------------------------------------
Write-Host "`n[3/4] Checking Node.js and frontend dependencies..." -ForegroundColor Yellow
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Error "'npm' was not found in PATH. Please install Node.js from https://nodejs.org/"
    exit 1
}

$NodeModulesDir = Join-Path $FrontendDir "node_modules"
if (-not (Test-Path $NodeModulesDir)) {
    Write-Host "  -> node_modules not found in frontend\. Running 'npm install'..." -ForegroundColor Gray
    Push-Location $FrontendDir
    try {
        & npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to install frontend dependencies."
            exit 1
        }
        Write-Host "  -> Frontend dependencies installed successfully." -ForegroundColor Green
    } finally {
        Pop-Location
    }
} else {
    Write-Host "  -> Frontend node_modules already present." -ForegroundColor Green
}

# ------------------------------------------------------------------------------
# 3. Launch Backend and Frontend
# ------------------------------------------------------------------------------
Write-Host "`n[4/4] Launching Backend and Frontend..." -ForegroundColor Yellow
Write-Host "  -> Backend:  http://localhost:8000 (API & Docs at /docs)" -ForegroundColor Gray
Write-Host "  -> Frontend: http://localhost:5173" -ForegroundColor Gray
Write-Host "==================================================" -ForegroundColor Cyan

# Start Backend in a new window
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$BackendDir`" && `"$VenvPython`" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000"
# Start Frontend in a new window
Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d `"$FrontendDir`" && npm run dev"

Write-Host "Both servers launched in separate terminal windows." -ForegroundColor Green
Write-Host "Close those windows or press Ctrl+C in them to stop each server." -ForegroundColor Gray
