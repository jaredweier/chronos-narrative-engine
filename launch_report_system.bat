@echo off
title Chronos Narrative Engine
echo ========================================
echo  Chronos Narrative Engine
echo  Law Enforcement Report Generation System
echo ========================================
echo.

cd /d "%~dp0"

if not exist "venv" (
    echo ERROR: Virtual environment not found.
    echo Please run automate_infra_setup.ps1 first.
    echo.
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo Starting Chronos Narrative Engine...
echo The application will open in your default browser.
echo Press Ctrl+C to stop the server.
echo.

streamlit run app.py --server.address=0.0.0.0 --server.port=8501

pause
