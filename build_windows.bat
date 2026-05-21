@echo off
REM Script de compilation d'Echo pour Windows
REM Usage : build_windows.bat [--clean] [--dev]
REM   --clean  supprime les builds precedents avant de compiler
REM   --dev    compile avec MODE_DEV=True (defaut : MODE_DEV=False)
REM Prerequis : Python 3.10+, pip
REM Sortie : dist\Echo\Echo.exe

setlocal enabledelayedexpansion

cd /d "%~dp0"

REM Lecture des arguments (ordre libre)
set OPT_CLEAN=0
set OPT_DEV=0
for %%A in (%*) do (
    if "%%A"=="--clean" set OPT_CLEAN=1
    if "%%A"=="--dev"   set OPT_DEV=1
)

if "!OPT_DEV!"=="1" (
    echo === Compilation d'Echo pour Windows [MODE DEV] ===
) else (
    echo === Compilation d'Echo pour Windows [RELEASE] ===
)
echo Repertoire : %CD%

REM --- Nettoyage ---
if "!OPT_CLEAN!"=="1" (
    echo [1/5] Nettoyage des builds precedents...
    if exist build rmdir /s /q build
    if exist dist  rmdir /s /q dist
    if exist Echo.spec del Echo.spec
)

REM --- Detection Python / virtualenv ---
set PYTHON=python
set PIP=pip

if exist ".venv\Scripts\python.exe" (
    set PYTHON=.venv\Scripts\python.exe
    set PIP=.venv\Scripts\pip.exe
    echo [2/5] Virtualenv detecte : .venv
) else if exist "venv\Scripts\python.exe" (
    set PYTHON=venv\Scripts\python.exe
    set PIP=venv\Scripts\pip.exe
    echo [2/5] Virtualenv detecte : venv
) else (
    echo [2/5] Python systeme utilise
)

REM --- Patch MODE_DEV dans parametres.py ---
copy parametres.py parametres.py.bak_build >nul

if "!OPT_DEV!"=="0" (
    echo [3/5] MODE_DEV desactive pour la release...
    %PYTHON% -c "import re; f=open('parametres.py','r'); c=f.read(); f.close(); c=re.sub(r'^(MODE_DEV\s*=\s*)True', r'\1False', c, flags=re.MULTILINE); f=open('parametres.py','w'); f.write(c); f.close()"
    if errorlevel 1 (
        echo ERREUR : impossible de patcher parametres.py
        copy parametres.py.bak_build parametres.py >nul
        del parametres.py.bak_build
        pause
        exit /b 1
    )
) else (
    echo [3/5] MODE_DEV conserve ^(--dev^)...
)

REM --- Installation de PyInstaller ---
echo [4/5] Installation de PyInstaller...
%PIP% install --quiet pyinstaller
if errorlevel 1 (
    echo ERREUR : impossible d'installer PyInstaller.
    copy parametres.py.bak_build parametres.py >nul
    del parametres.py.bak_build
    pause
    exit /b 1
)

REM --- Compilation ---
echo [5/5] Compilation en cours (peut prendre 1-2 minutes)...
%PYTHON% -m PyInstaller ^
    --name "Echo" ^
    --onedir ^
    --noconsole ^
    --add-data "assets;assets" ^
    --add-data "demon_slime.json;." ^
    --add-data "map.json;." ^
    --add-data "favicon.ico;." ^
    --add-data "favicon.png;." ^
    --hidden-import "xml.etree.ElementTree" ^
    --hidden-import "xml.etree.cElementTree" ^
    --hidden-import "numpy" ^
    --hidden-import "pygame" ^
    --hidden-import "pygame.mixer" ^
    --hidden-import "pygame.font" ^
    --icon "favicon.ico" ^
    --noconfirm ^
    main.py

REM --- Restauration de parametres.py ---
copy parametres.py.bak_build parametres.py >nul
del parametres.py.bak_build
echo [INFO] parametres.py restaure.

if errorlevel 1 (
    echo ERREUR : la compilation a echoue.
    pause
    exit /b 1
)

echo.
echo Compilation terminee !
echo Executable : dist\Echo\Echo.exe
echo Pour distribuer : compressez le dossier dist\Echo\ en zip.
echo.
pause
