@echo off
chcp 65001 >nul 2>nul
setlocal
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

rem Le lanceur "py" est le plus fiable : "python" peut renvoyer vers le
rem raccourci du Microsoft Store, qui n'execute rien. On teste dans cet
rem ordre, un candidat par ligne pour eviter les blocs imbriques de cmd.
set "PY="
where py      >nul 2>nul && set "PY=py -3"
if defined PY goto lancer
where python  >nul 2>nul && set "PY=python"
if defined PY goto lancer
where python3 >nul 2>nul && set "PY=python3"
if defined PY goto lancer

echo.
echo   Python 3 est introuvable sur cet ordinateur.
echo.
echo   Installez-le depuis https://www.python.org/downloads/
echo   et cochez "Add python.exe to PATH" pendant l'installation.
echo.
pause
exit /b 1

:lancer
%PY% admin\publier.py
echo.
pause
