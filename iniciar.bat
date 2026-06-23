@echo off
echo Iniciando o Sistema 4X CRM...
echo.
cd /d "%~dp0"
start "" "http://localhost:5000"
python app.py
pause
