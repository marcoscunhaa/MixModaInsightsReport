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
    pause
    exit /b 1
)
pyinstaller --noconfirm --clean --onefile --windowed --collect-all keyring --collect-all rapidfuzz --name MixModaInsights --add-data "data\catalogo_produtos_estoque_geral.json;data" app.py
echo.
echo ==========================================
echo EXECUTAVEL GERADO EM:
echo dist\MixModaInsights.exe
echo ==========================================
pause
