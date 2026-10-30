@echo off
title Gerador - Mix Moda Insights
rem Uso:
rem   build.bat          -> dist\MixModaInsights.exe (arquivo unico; abre mais devagar)
rem   build.bat pasta    -> dist\MixModaInsights\MixModaInsights.exe (pasta; abre bem mais rapido)
set MODO=--onefile
set SAIDA=dist\MixModaInsights.exe
if /I "%~1"=="pasta" (
    set MODO=--onedir
    set SAIDA=dist\MixModaInsights\MixModaInsights.exe
)
echo ==========================================
echo       GERANDO MIX MODA INSIGHTS %MODO%
echo ==========================================
echo.
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo ERRO ao instalar dependencias.
    if not defined CI pause
    exit /b 1
)
rem xlrd/openpyxl/lxml sao carregados pelo pandas so na hora de ler a planilha;
rem sem os --hidden-import o .exe nao abre arquivos .xls/.xlsx.
rem --splash mostra a tela de abertura enquanto o aplicativo carrega.
python -m PyInstaller --noconfirm --clean %MODO% --windowed --collect-all rapidfuzz ^
  --hidden-import xlrd --hidden-import openpyxl --hidden-import lxml.etree ^
  --exclude-module tkinter --splash assets\splash.png ^
  --name MixModaInsights --add-data "data\catalogo_produtos_estoque_geral.json;data" app.py
if errorlevel 1 (
    echo.
    echo ERRO ao gerar o executavel.
    if not defined CI pause
    exit /b 1
)
echo.
echo ==========================================
echo EXECUTAVEL GERADO EM:
echo %SAIDA%
echo ==========================================
if not defined CI pause
