@echo off
title Builder - Mix Moda Insights
rem Usage:
rem   build.bat          -> dist\MixModaInsights.exe (single file; slower to open)
rem   build.bat folder   -> dist\MixModaInsights\MixModaInsights.exe (folder; opens much faster)
set MODE=--onefile
set OUTPUT=dist\MixModaInsights.exe
if /I "%~1"=="folder" (
    set MODE=--onedir
    set OUTPUT=dist\MixModaInsights\MixModaInsights.exe
)
echo ==========================================
echo       BUILDING MIX MODA INSIGHTS %MODE%
echo ==========================================
echo.
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERROR installing dependencies.
    if not defined CI pause
    exit /b 1
)
rem xlrd/openpyxl/lxml are only loaded by pandas when a spreadsheet is read;
rem without --hidden-import the .exe cannot open .xls/.xlsx files.
rem --splash shows the splash screen while the app loads.
python -m PyInstaller --noconfirm --clean %MODE% --windowed --collect-all rapidfuzz ^
  --hidden-import xlrd --hidden-import openpyxl --hidden-import lxml.etree ^
  --exclude-module tkinter --splash assets\splash.png ^
  --name MixModaInsights --add-data "data\catalogo_produtos_estoque_geral.json;data" app.py
if errorlevel 1 (
    echo.
    echo ERROR building the executable.
    if not defined CI pause
    exit /b 1
)
echo.
echo ==========================================
echo EXECUTABLE CREATED AT:
echo %OUTPUT%
echo ==========================================
if not defined CI pause
