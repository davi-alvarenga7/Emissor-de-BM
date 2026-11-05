@echo off
cd /d "%~dp0"
set PYTHONPATH=%~dp0
echo Iniciando E-BM - Emissor de Boletim de Medição...
python -m src
if errorlevel 1 (
    echo.
    echo ERRO: O programa nao pôde ser iniciado.
    echo Verifique se o Python esta instalado e se as dependencias foram instaladas:
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
