@echo off
REM ============================================================================
REM Launch script for the Component Tag Checker GUI.
REM ============================================================================

echo Starting Component Tag Checker GUI...

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Python is not installed or not in the PATH
    echo Please install Python 3.6 or higher and try again.
    echo.
    echo Press any key to exit...
    pause > nul
    exit /b 1
)

REM Check if tkinter is available
python -c "import tkinter" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: tkinter is not available in your Python installation
    echo Please install tkinter and try again.
    echo.
    echo Press any key to exit...
    pause > nul
    exit /b 1
)

REM Check if the GUI script exists
if not exist "check_component_tags_gui.py" (
    echo Error: check_component_tags_gui.py not found
    echo Please make sure the file is in the same directory as this batch file.
    echo.
    echo Press any key to exit...
    pause > nul
    exit /b 1
)

REM Check if the component tag checker script exists
if not exist "check_component_tags.py" (
    echo Error: check_component_tags.py not found
    echo Please make sure the file is in the same directory as this batch file.
    echo.
    echo Press any key to exit...
    pause > nul
    exit /b 1
)

REM Launch the GUI
python check_component_tags_gui.py

REM Check if the GUI launched successfully
if %ERRORLEVEL% neq 0 (
    echo Error: Failed to launch the Component Tag Checker GUI
    echo.
    echo Press any key to exit...
    pause > nul
    exit /b 1
)

exit /b 0
