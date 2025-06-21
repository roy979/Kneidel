@echo off
REM Get the absolute path of the directory where this batch file is located
set SCRIPT_DIR=%~dp0

REM Use the virtual environment's Python directly
"%SCRIPT_DIR%Kneidel_venv\Scripts\python.exe" "%SCRIPT_DIR%Scripts\Prepare_Songs.py"

REM Pause to keep the window open if there's an error
pause