@echo off
REM Build script for Echo on Windows
REM Usage: packaging\build_windows.bat [--clean] [--dev]
REM   --clean  remove the previous builds before compiling
REM   --dev    build with DEV_MODE=True (default: DEV_MODE=False)
REM Requirements: Python 3.10+, pip
REM Output: dist\Echo.exe (single self-contained executable)

setlocal enabledelayedexpansion

cd /d "%~dp0.."

REM Parse the arguments (any order)
set OPT_CLEAN=0
set OPT_DEV=0
for %%A in (%*) do (
    if "%%A"=="--clean" set OPT_CLEAN=1
    if "%%A"=="--dev"   set OPT_DEV=1
)

if "!OPT_DEV!"=="1" (
    echo === Building Echo for Windows [DEV MODE] ===
) else (
    echo === Building Echo for Windows [RELEASE] ===
)
echo Directory: %CD%

REM --- Cleaning ---
if "!OPT_CLEAN!"=="1" (
    echo [1/5] Removing the previous builds...
    if exist build rmdir /s /q build
    if exist dist  rmdir /s /q dist
)

REM --- Python / virtualenv detection ---
set PYTHON=python
set PIP=pip

if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
    set PIP=.venv\Scripts\pip.exe
    echo [2/5] Virtualenv found: .venv
) else if exist "venv\Scripts\python.exe" (
    set PYTHON=venv\Scripts\python.exe
    set PIP=venv\Scripts\pip.exe
    echo [2/5] Virtualenv found: venv
) else (
    echo [2/5] Using the system Python
)

REM --- Patch DEV_MODE in settings.py ---
copy settings.py settings.py.bak_build >nul

if "!OPT_DEV!"=="0" (
    echo [3/5] DEV_MODE disabled for the release...
    %PYTHON% -c "import re; f=open('settings.py','r',encoding='utf-8'); c=f.read(); f.close(); c=re.sub(r'^(DEV_MODE\s*=\s*)True', r'\1False', c, flags=re.MULTILINE); f=open('settings.py','w',encoding='utf-8'); f.write(c); f.close()"
    if errorlevel 1 (
        echo ERROR: cannot patch settings.py
        copy settings.py.bak_build settings.py >nul
        del settings.py.bak_build
        pause
        exit /b 1
    )
) else (
    echo [3/5] DEV_MODE kept ^(--dev^)...
)

REM --- PyInstaller ---
echo [4/5] Installing PyInstaller...
%PIP% install --quiet pyinstaller
if errorlevel 1 (
    echo ERROR: cannot install PyInstaller.
    copy settings.py.bak_build settings.py >nul
    del settings.py.bak_build
    pause
    exit /b 1
)

REM --- Build ---
echo [5/5] Building (can take 2-4 minutes)...
%PYTHON% -m PyInstaller ^
    --name "Echo" ^
    --onefile ^
    --noconsole ^
    --add-data "assets;assets" ^
    --hidden-import "xml.etree.ElementTree" ^
    --hidden-import "numpy" ^
    --hidden-import "pygame" ^
    --hidden-import "pygame.mixer" ^
    --hidden-import "pygame.font" ^
    --icon "assets/favicon.ico" ^
    --noconfirm ^
    main.py
set BUILD_STATUS=!errorlevel!

REM --- Restore settings.py ---
copy settings.py.bak_build settings.py >nul
del settings.py.bak_build
echo [INFO] settings.py restored.

if not "!BUILD_STATUS!"=="0" (
    echo ERROR: the build failed.
    pause
    exit /b 1
)

echo.
echo Build finished!
echo Executable: dist\Echo.exe (single self-contained file)
echo To distribute it: send dist\Echo.exe, nothing else is needed
echo.
pause
