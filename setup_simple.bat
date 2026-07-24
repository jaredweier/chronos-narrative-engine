@echo off
title Chronos Narrative Engine - Setup
echo ========================================
echo  Chronos Narrative Engine Setup
echo ========================================
echo.

cd /d "%~dp0"

echo [1/4] Creating Python virtual environment...
if not exist "venv" (
    python -m venv venv
    echo   Virtual environment created
) else (
    echo   Virtual environment already exists
)

echo.
echo [2/4] Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo [3/4] Installing Python packages...
pip install --upgrade pip --quiet
pip install streamlit faster-whisper pdfplumber requests torch pydantic python-docx reportlab --quiet
echo   Packages installed

echo.
echo [4/4] Creating directories...
if not exist "temp_processing" mkdir temp_processing
if not exist "completed_reports" mkdir completed_reports
if not exist "officer_profiles" mkdir officer_profiles
echo   Directories created

echo.
echo ========================================
echo  Setup Complete!
echo ========================================
echo.
echo To launch: Double-click 'launch_report_system.bat'
echo.
pause
