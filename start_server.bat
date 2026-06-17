@echo off
cd /d "%~dp0"

echo ============================================
echo  Installing dependencies...
echo ============================================
python -m pip uninstall -y psycopg2-binary >nul 2>nul
python -m pip install -r requirements.txt

echo.
echo ============================================
echo  Starting server...
echo  Open in browser: http://127.0.0.1:5000
echo  To stop the server - close this window.
echo ============================================
echo.

python app.py

pause
