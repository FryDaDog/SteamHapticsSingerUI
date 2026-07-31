@echo off
REM build.bat
REM
REM builds steam_haptics_ui.py into a standalone .exe
REM uses a local python venv
 
setlocal enabledelayedexpansion
 
python -c "import tkinter" 2>nul
if errorlevel 1 (
    echo tkinter isn't installed or python isn't on PATH.
    echo Grab the official installer from python.org - it ships with tkinter by default.
    exit /b 1
)
 
set APP_NAME=steam-haptics-ui
set ENTRYPOINT=steam_haptics_ui.py
set VENV=.venv
 
echo ==^> Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist __pycache__ rmdir /s /q __pycache__
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"
 
if not exist "%VENV%" (
    echo ==^> Creating virtual environment...
    python -m venv "%VENV%"
    if errorlevel 1 (
        echo Failed to create virtual environment.
        exit /b 1
    )
)
 
echo ==^> Activating virtual environment...
call "%VENV%\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    exit /b 1
)
 
echo ==^> Updating pip...
python -m pip install --upgrade pip wheel
if errorlevel 1 (
    echo pip upgrade failed.
    exit /b 1
)
 
echo ==^> Installing build dependencies...
python -m pip install --upgrade pyinstaller
if errorlevel 1 (
    echo Installing pyinstaller failed.
    exit /b 1
)
 
echo ==^> Building...
pyinstaller ^
    --clean ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "%APP_NAME%" ^
    --add-data "SteamHapticsLogo.png;." ^
    "%ENTRYPOINT%"
 
if errorlevel 1 (
    echo Build failed.
    exit /b 1
)
 

where upx >nul 2>nul
if not errorlevel 1 (
    echo ==^> Compressing binary with UPX...
    upx --best --lzma "dist\%APP_NAME%.exe"
)
 
echo.
echo Build complete!
echo Binary: dist\%APP_NAME%.exe
 
endlocal
