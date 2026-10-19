@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   Starting Austria Tech Jobs Hub + Overleaf Services
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
        echo ...still starting Docker...
        goto wait_docker
    )
    echo Docker engine is now ready!
) else (
    echo Docker engine is already running.
)

:: 2. Start Overleaf Toolkit container
set "OVERLEAF_DIR=%USERPROFILE%\Desktop\CV\overleaf-toolkit"
if exist "!OVERLEAF_DIR!\config\overleaf.rc" (
    echo [2/3] Starting Overleaf container in background...
    pushd "!OVERLEAF_DIR!"
    if exist "C:\Program Files\Git\bin\bash.exe" (
        "C:\Program Files\Git\bin\bash.exe" -c "bin/up -d"
    ) else (
        docker compose -f lib/docker-compose.base.yml -f config/docker-compose.override.yml up -d
    )
    popd
    echo Overleaf is running at http://localhost:80
) else (
    echo [2/3] Overleaf Toolkit not found at !OVERLEAF_DIR!. Skipping.
)

:: 3. Start local Austria Tech Jobs Hub server
echo [3/3] Starting Austria Tech Jobs Hub on http://localhost:8765 ...
start http://localhost:8765
python "%~dp0scripts\resume_server.py"

pause
