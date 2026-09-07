@echo off
title BCut Subtitle Tool - Installer Builder
echo ============================================================
echo   BCut Subtitle Tool - Installer Builder
echo   Compression: UPX + LZMA2 ultra64 solid (minimal size)
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] Checking Python...
"C:\Users\Administrator\AppData\Local\Python\pythoncore-3.12-64\python.exe" --version
if errorlevel 1 (
    echo.
    echo [ERROR] Python 3.12 not found!
    pause
    exit /b 1
)

echo.
echo [2/3] Checking UPX...
if exist "C:\upx-5.1.1-win64\upx.exe" (
    echo   UPX found: C:\upx-5.1.1-win64\upx.exe
) else (
    echo   [WARN] UPX not found, will skip UPX compression
)

echo.
echo [3/3] Building installer (PyInstaller + Inno Setup)...
echo   This may take 3-10 minutes, please wait...
echo.

"C:\Users\Administrator\AppData\Local\Python\pythoncore-3.12-64\python.exe" build_installer.py

echo.
echo ============================================================
echo   Build complete!
echo   Installer: installer\BCut_Subtitle_Tool_v1.0_setup.exe
echo ============================================================
echo.
pause
