@echo off
set "PYTHON_EXE=C:\Users\Administrator\AppData\Local\Python\pythoncore-3.12-64\python.exe"
set "SCRIPT=%~dp0fix_ffmpeg.py"

if not exist "%PYTHON_EXE%" (
    echo Python not found at: %PYTHON_EXE%
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%SCRIPT%"
