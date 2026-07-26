@echo off
REM QwenChat Windows launcher — add this scripts\ folder to your user PATH.
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"

if not defined QWENCHAT_HOME set "QWENCHAT_HOME=%ROOT%"
cd /d "%QWENCHAT_HOME%" 2>nul
if errorlevel 1 (
  echo Error: QWENCHAT_HOME is invalid: %QWENCHAT_HOME%
  exit /b 1
)

if exist "%QWENCHAT_HOME%\.venv\Scripts\python.exe" (
  "%QWENCHAT_HOME%\.venv\Scripts\python.exe" -m qwenchat %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python -m qwenchat %*
  exit /b %ERRORLEVEL%
)

echo Error: Python not found. Create a venv in the project and install deps:
echo   cd "%QWENCHAT_HOME%"
echo   python -m venv .venv
echo   .venv\Scripts\activate
echo   pip install -r requirements.txt
echo   pip install -e .
exit /b 1
