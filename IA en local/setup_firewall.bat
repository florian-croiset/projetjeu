@echo off
echo ========================================
echo Configuration Firewall pour le Jeu
echo ========================================
echo.
echo Ce script va autoriser le jeu dans le firewall Windows.
echo Necessite les droits Administrateur !
echo.
pause

REM Verifier les droits administrateur
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo.
    echo [ERREUR] Ce script doit etre execute en tant qu'Administrateur !
    echo.
    echo Faites un clic droit sur le fichier et choisissez "Executer en tant qu'administrateur"
    echo.
    pause
    exit /b 1
)

echo.
echo [1/3] Creation de la regle pour le PORT 5555...
netsh advfirewall firewall delete rule name="Jeu Python - Port 5555" >nul 2>&1
netsh advfirewall firewall add rule name="Jeu Python - Port 5555" dir=in action=allow protocol=TCP localport=5555
if %errorLevel% NEQ 0 (
    echo [ERREUR] Impossible de creer la regle du port
    pause
    exit /b 1
)
echo [OK] Port 5555 autorise

echo.
echo [2/3] Autorisation de Python.exe...
for /f "delims=" %%i in ('where python 2^>nul') do set PYTHON_PATH=%%i
if defined PYTHON_PATH (
    netsh advfirewall firewall delete rule name="Python - Jeu Reseau" >nul 2>&1
    netsh advfirewall firewall add rule name="Python - Jeu Reseau" dir=in action=allow program="%PYTHON_PATH%" enable=yes
    echo [OK] Python autorise : %PYTHON_PATH%
) else (
    echo [ATTENTION] Python.exe introuvable dans PATH
    echo La regle du port 5555 suffit normalement
)

echo.
echo [3/3] Verification...
netsh advfirewall firewall show rule name="Jeu Python - Port 5555" >nul 2>&1
if %errorLevel% EQU 0 (
    echo [OK] Configuration terminee avec succes !
) else (
    echo [ERREUR] La regle n'a pas ete creee correctement
)

echo.
echo ========================================
echo Configuration terminee !
echo ========================================
echo.
echo Vous pouvez maintenant lancer le jeu.
echo Cette configuration est permanente.
echo.
pause