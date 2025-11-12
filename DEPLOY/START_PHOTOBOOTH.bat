@echo off
title AI Photo Booth Launcher
color 0A
echo.
echo ========================================
echo    AI PHOTO BOOTH - Starting...
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found!
    echo Please install Python 3.x from python.org
    echo.
    pause
    exit /b 1
)

REM Check if .NET Runtime is installed
dotnet --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] .NET Runtime not detected!
    echo Download from: https://dotnet.microsoft.com/download/dotnet/8.0
    echo.
    echo Attempting to start anyway...
    timeout /t 3 /nobreak >nul
)

REM Check if Google API key is configured
if not exist "python_server\.env" (
    echo [WARNING] .env file not found!
    echo Creating template .env file...
    echo GOOGLE_API_KEY=your_api_key_here> python_server\.env
    echo WATCH_DIR=../input>> python_server\.env
    echo.
    echo Please edit python_server\.env and add your Google API key!
    echo Press any key to continue anyway, or close this window to exit.
    pause >nul
)

REM Start camera bridge in background
echo [1/3] Starting Camera Bridge...
start "Camera Bridge" /MIN cmd /c "camera_bridge\NikonBridge.exe"
timeout /t 3 /nobreak >nul

REM Check if dependencies are installed
if not exist "python_server\__pycache__" (
    echo [2/3] First run detected - Installing Python dependencies...
    cd python_server
    pip install -r requirements.txt --quiet
    cd ..
    echo Dependencies installed!
    echo.
)

REM Start Python server
echo [3/3] Starting Web Server...
echo.
echo ========================================
echo   Photo Booth is ready!
echo   Open your browser to:
echo   http://localhost:8000
echo ========================================
echo.
echo Press Ctrl+C to stop both servers
echo.

cd python_server
python -m uvicorn server:app --host 0.0.0.0 --port 8000

REM Cleanup on exit
echo.
echo Shutting down...
taskkill /IM NikonBridge.exe /F >nul 2>&1
echo Done!
timeout /t 2 /nobreak >nul
