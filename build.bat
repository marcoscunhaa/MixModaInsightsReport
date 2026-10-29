@echo off
title Gerador - Mix Moda Insights
echo ==========================================
echo       GERANDO MIX MODA INSIGHTS
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
python -m PyInstaller --noconfirm --clean --onefile --windowed --collect-all rapidfuzz ^
  --hidden-import xlrd --hidden-import openpyxl --hidden-import lxml.etree ^
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
echo dist\MixModaInsights.exe
echo ==========================================
if not defined CI pause
