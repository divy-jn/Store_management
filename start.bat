@echo off
setlocal enabledelayedexpansion
title Purplle Store Intelligence

echo =======================================================
echo     Starting Purplle Store Intelligence API ^& UI
echo =======================================================
echo.

:: 1. Check if Docker is installed
where docker >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is not installed or not in your PATH.
    echo Please install Docker Desktop from https://www.docker.com/products/docker-desktop/
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

:: 2. Check if Docker Engine is running
echo [1/4] Checking Docker Engine status...
docker info >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Docker is installed but the engine is not running!
    echo Please open Docker Desktop and wait for it to start.
    echo Press any key to exit...
    pause >nul
    exit /b 1
)
echo [OK] Docker is running!

:: 3. Build and start containers
echo.
echo [2/4] Building and starting Docker containers...
docker compose up --build -d
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Failed to start containers! 
    echo This is usually because a port ^(8000 for API, 3000 for UI, or 5432 for DB^) is already in use by another application.
    echo.
    echo --- Container Logs ---
    docker compose logs --tail=15
    echo ----------------------
    echo Press any key to exit...
    pause >nul
    exit /b 1
)

:: 4. Wait for initialization
echo.
echo [3/4] Waiting for database and API to initialize...
timeout /t 5 /nobreak > NUL

:: 5. Launch Browser
echo.
echo [4/4] Launching Dashboard in your default browser...
start http://localhost:3000

echo.
echo =======================================================
echo   Services are running successfully!
echo.
echo   Dashboard : http://localhost:3000
echo   API Docs  : http://localhost:8000/docs
echo   Health    : http://localhost:8000/health
echo =======================================================
echo.
echo Keep this window open. 
echo Press any key to stop all services and gracefully exit...
pause > NUL

echo.
echo Stopping containers...
docker compose down
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Some containers may not have stopped correctly.
) else (
    echo [OK] All services stopped successfully.
)
echo Goodbye!
timeout /t 2 > NUL
