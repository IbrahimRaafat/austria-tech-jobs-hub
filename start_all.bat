@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   Starting Austria Tech Jobs Hub + Overleaf in Docker
echo ========================================================

:: 1. Check & start Docker Desktop
echo [1/3] Checking Docker engine...
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo Docker engine is stopped. Launching Docker Desktop...
    start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    echo Waiting for Docker engine to become ready (this may take 20-30 seconds)...
    
    :wait_docker
    timeout /t 4 /nobreak >nul
    docker info >nul 2>&1
    if %errorlevel% neq 0 (
        echo ...waiting for Docker engine...
        goto wait_docker
    )
    echo Docker engine is now ready!
) else (
    echo Docker engine is already running.
)

:: 2. Launch unified Docker Compose stack
echo [2/3] Starting all services via Docker Compose...
cd /d "%~dp0"
docker compose up -d

if %errorlevel% equ 0 (
    echo.
    echo ========================================================
    echo   All services are up and running!
    echo   - Austria Tech Jobs Hub : http://localhost:8765
    echo   - Overleaf LaTeX Editor : http://localhost:80
    echo ========================================================
    echo.
    start http://localhost:8765
) else (
    echo.
    echo [Fallback] Docker compose encountered an issue. Starting local Python server directly...
    start http://localhost:8765
    python "%~dp0scripts\resume_server.py"
)

pause
