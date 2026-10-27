@echo off
cd /d "%~dp0"
if not exist venv (
  echo Creating virtual environment...
  python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt
echo.
echo Open http://127.0.0.1:5000 in your browser. Keep this window open.
echo.
python app.py
pause
