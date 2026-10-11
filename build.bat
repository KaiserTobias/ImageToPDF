@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo  ImageToPDF - portable Version bauen
echo ===============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo FEHLER: Python wurde nicht gefunden. Bitte Python 3.10 oder neuer installieren
    echo         und beim Setup "Add python.exe to PATH" aktivieren.
    pause
    exit /b 1
)

echo [1/4] Virtuelle Umgebung anlegen ...
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 ( echo FEHLER beim Anlegen der virtuellen Umgebung. & pause & exit /b 1 )
)
set PY=.venv\Scripts\python.exe

echo [2/4] Bibliotheken installieren ...
"%PY%" -m pip install --upgrade pip --quiet
"%PY%" -m pip install -r requirements.txt --quiet
if errorlevel 1 ( echo FEHLER beim Installieren der Bibliotheken. & pause & exit /b 1 )

echo [3/4] Tests ausfuehren ...
"%PY%" -m pytest -q tests
if errorlevel 1 (
    echo FEHLER: Tests fehlgeschlagen. Build abgebrochen.
    pause
    exit /b 1
)

echo [4/4] EXE bauen (das dauert ein bis zwei Minuten) ...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
"%PY%" -m PyInstaller --noconfirm --clean --windowed --name ImageToPDF ^
    --collect-all customtkinter ^
    --collect-all tkinterdnd2 ^
    --hidden-import PIL._tkinter_finder ^
    --paths src ^
    run_imagetopdf.py
if errorlevel 1 ( echo FEHLER beim Bauen der EXE. & pause & exit /b 1 )

copy /y ANLEITUNG.md dist\ImageToPDF\ >nul

echo.
echo ===============================================
echo  Fertig. Portable Version liegt in:
echo    dist\ImageToPDF\ImageToPDF.exe
echo  Den ganzen Ordner "dist\ImageToPDF" als ZIP weitergeben.
echo ===============================================
pause
