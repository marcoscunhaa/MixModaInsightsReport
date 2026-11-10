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
rem Os --exclude-module tiram do pacote o que o app nao usa (outros bindings Qt,
rem modulos Qt extras, backends de grafico de outras bibliotecas e testes):
rem executavel menor, abre mais rapido e ocupa menos memoria.
rem O app usa so QtCore, QtGui e QtWidgets do PySide6 e o backend QtAgg do matplotlib.
set EXCLUIR=--exclude-module tkinter --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2 ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets --exclude-module PySide6.QtWebEngineQuick ^
  --exclude-module PySide6.QtWebChannel --exclude-module PySide6.QtWebSockets --exclude-module PySide6.QtQml ^
  --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQuickWidgets --exclude-module PySide6.Qt3DCore ^
  --exclude-module PySide6.Qt3DRender --exclude-module PySide6.QtMultimedia --exclude-module PySide6.QtMultimediaWidgets ^
  --exclude-module PySide6.QtCharts --exclude-module PySide6.QtDataVisualization --exclude-module PySide6.QtGraphs ^
  --exclude-module PySide6.QtPdf --exclude-module PySide6.QtPdfWidgets --exclude-module PySide6.QtBluetooth ^
  --exclude-module PySide6.QtPositioning --exclude-module PySide6.QtLocation --exclude-module PySide6.QtSensors ^
  --exclude-module PySide6.QtSerialPort --exclude-module PySide6.QtSql --exclude-module PySide6.QtTest ^
  --exclude-module PySide6.QtDesigner --exclude-module PySide6.QtHelp --exclude-module PySide6.QtUiTools ^
  --exclude-module matplotlib.backends.backend_tkagg --exclude-module matplotlib.backends.backend_wxagg ^
  --exclude-module matplotlib.backends.backend_gtk3agg --exclude-module matplotlib.backends.backend_gtk4agg ^
  --exclude-module matplotlib.backends.backend_webagg --exclude-module matplotlib.backends.backend_nbagg ^
  --exclude-module IPython --exclude-module jupyter_client --exclude-module notebook ^
  --exclude-module pytest --exclude-module _pytest --exclude-module matplotlib.tests ^
  --exclude-module numpy.tests --exclude-module pandas.tests --exclude-module PIL.ImageTk
python -m PyInstaller --noconfirm --clean %MODO% --windowed --collect-all rapidfuzz ^
  --hidden-import xlrd --hidden-import openpyxl --hidden-import lxml.etree ^
  %EXCLUIR% --splash assets\splash.png ^
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
