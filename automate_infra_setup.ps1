#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Chronos Narrative Engine - Automated Infrastructure Setup
.DESCRIPTION
    Installs all dependencies for the offline law enforcement report generation system.
    Requires Administrator privileges.
.NOTES
    Device: Investigative-Workstation
    GPU: NVIDIA GeForce RTX 5070 Ti (16 GB VRAM)
    CPU: AMD Ryzen 9 9950X (16-Core / 32-Threads)
#>

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Chronos Narrative Engine Setup" -ForegroundColor Cyan
Write-Host " Automated Infrastructure Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check for Administrator privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "ERROR: This script requires Administrator privileges." -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Step 1: Install NVIDIA CUDA via winget
Write-Host "`n[1/6] Installing NVIDIA CUDA Toolkit..." -ForegroundColor Yellow
try {
    winget install Nvidia.CUDA --silent --accept-package-agreements --accept-source-agreements
    Write-Host "  CUDA installed successfully" -ForegroundColor Green
} catch {
    Write-Host "  CUDA installation failed: $_" -ForegroundColor Red
    Write-Host "  Continuing with setup..." -ForegroundColor Yellow
}

# Step 2: Install Ollama via winget
Write-Host "`n[2/6] Installing Ollama..." -ForegroundColor Yellow
try {
    winget install Ollama.Ollama --silent --accept-package-agreements --accept-source-agreements
    Write-Host "  Ollama installed successfully" -ForegroundColor Green
} catch {
    Write-Host "  Ollama installation failed: $_" -ForegroundColor Red
    Write-Host "  Continuing with setup..." -ForegroundColor Yellow
}

# Step 3: Download and install FFmpeg
Write-Host "`n[3/6] Installing FFmpeg..." -ForegroundColor Yellow
$ffmpegUrl = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
$ffmpegZip = Join-Path $env:TEMP "ffmpeg.zip"
$ffmpegDir = "C:\ffmpeg"

try {
    if (-not (Test-Path $ffmpegDir)) {
        Write-Host "  Downloading FFmpeg..."
        Invoke-WebRequest -Uri $ffmpegUrl -OutFile $ffmpegZip -UseBasicParsing
        
        Write-Host "  Extracting FFmpeg..."
        Expand-Archive -Path $ffmpegZip -DestinationPath $ffmpegDir -Force
        
        # Find the bin directory
        $binDir = Get-ChildItem -Path $ffmpegDir -Recurse -Filter "bin" -Directory | Select-Object -First 1
        
        if ($binDir) {
            # Add to system PATH
            $currentPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
            if ($currentPath -notlike "*$($binDir.FullName)*") {
                [Environment]::SetEnvironmentVariable("Path", "$currentPath;$($binDir.FullName)", "Machine")
                $env:Path = "$env:Path;$($binDir.FullName)"
                Write-Host "  FFmpeg added to system PATH" -ForegroundColor Green
            }
        }
        
        Remove-Item $ffmpegZip -Force -ErrorAction SilentlyContinue
        Write-Host "  FFmpeg installed successfully" -ForegroundColor Green
    } else {
        Write-Host "  FFmpeg already installed" -ForegroundColor Green
    }
} catch {
    Write-Host "  FFmpeg installation failed: $_" -ForegroundColor Red
}

# Step 4: Create Python virtual environment
Write-Host "`n[4/6] Setting up Python virtual environment..." -ForegroundColor Yellow
$venvPath = Join-Path $ScriptDir "venv"

try {
    if (-not (Test-Path $venvPath)) {
        python -m venv $venvPath
        Write-Host "  Virtual environment created" -ForegroundColor Green
    } else {
        Write-Host "  Virtual environment already exists" -ForegroundColor Green
    }
    
    # Activate and install packages
    & "$venvPath\Scripts\Activate.ps1"
    
    Write-Host "  Upgrading pip..."
    python -m pip install --upgrade pip --quiet
    
    Write-Host "  Installing Python packages..."
    pip install streamlit faster-whisper pdfplumber requests torch pydantic python-docx reportlab --quiet
    
    Write-Host "  Python packages installed" -ForegroundColor Green
} catch {
    Write-Host "  Python setup failed: $_" -ForegroundColor Red
}

# Step 5: Pull Ollama model
Write-Host "`n[5/6] Pulling Llama 3.1:8b model..." -ForegroundColor Yellow
try {
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -PassThru | Out-Null
    Start-Sleep -Seconds 3
    
    ollama pull llama3.1:8b
    Write-Host "  Model pulled successfully" -ForegroundColor Green
} catch {
    Write-Host "  Model pull failed: $_" -ForegroundColor Red
    Write-Host "  You may need to run 'ollama pull llama3.1:8b' manually" -ForegroundColor Yellow
}

# Step 6: Create required directories
Write-Host "`n[6/6] Creating directory structure..." -ForegroundColor Yellow
$dirs = @(
    (Join-Path $ScriptDir "temp_processing"),
    (Join-Path $ScriptDir "completed_reports"),
    (Join-Path $ScriptDir "officer_profiles")
)

foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "  Directories created" -ForegroundColor Green

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To launch the Chronos Narrative Engine:" -ForegroundColor Yellow
Write-Host "  Double-click 'launch_report_system.bat'" -ForegroundColor White
Write-Host ""
Write-Host "Or manually run:" -ForegroundColor Yellow
Write-Host "  cd $ScriptDir" -ForegroundColor White
Write-Host "  venv\Scripts\activate" -ForegroundColor White
Write-Host "  streamlit run app.py" -ForegroundColor White
Write-Host ""
