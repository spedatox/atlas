@echo off
:: ATLAS — Windows Build Script
:: Run this on a Windows machine with Python 3.10+ installed.
:: Usage: double-click or run from command prompt in the project folder.

echo ========================================
echo  ATLAS — Windows Build
echo ========================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.10+ from python.org
    pause
    exit /b 1
)

:: Install dependencies
echo [1/3] Installing dependencies...
python -m pip install PySide6 pyinstaller --upgrade -q
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

:: Clean old build
echo [2/3] Cleaning previous build...
if exist dist\ATLAS rmdir /s /q dist\ATLAS
if exist build rmdir /s /q build

:: Build
echo [3/3] Building ATLAS.exe ...
python -m PyInstaller atlas.spec --noconfirm

if errorlevel 1 (
    echo.
    echo ERROR: Build failed. See output above.
    pause
    exit /b 1
)

echo.
echo ========================================
echo  BUILD SUCCESSFUL!
echo  Output: dist\ATLAS\ATLAS.exe
echo ========================================
echo.
pause
