@echo off
title Publish to GitHub
echo ============================================================
echo   Publish to GitHub - One Click
echo ============================================================
echo.

cd /d "%~dp0"

"C:\Users\Administrator\AppData\Local\Python\pythoncore-3.12-64\python.exe" publish.py

echo.
pause
