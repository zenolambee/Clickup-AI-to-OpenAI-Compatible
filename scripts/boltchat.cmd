@echo off
REM BoltChat Windows launcher — add this scripts\ folder to your user PATH.
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"

if not defined BOLTCHAT_HOME set "BOLTCHAT_HOME=%ROOT%"
cd /d "%BOLTCHAT_HOME%" 2>nul
if errorlevel 1 (
  echo Error: BOLTCHAT_HOME is invalid: %BOLTCHAT_HOME%
  exit /b 1
)

if exist "%BOLTCHAT_HOME%\.venv\Scripts\python.exe" (
  "%BOLTCHAT_HOME%\.venv\Scripts\python.exe" -m boltchat %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python -m boltchat %*
  exit /b %ERRORLEVEL%
)

echo Error: Python not found. Create a venv in the project and install deps:
echo   cd "%BOLTCHAT_HOME%"
echo   python -m venv .venv
echo   .venv\Scripts\activate
echo   pip install -r requirements.txt
echo   pip install -e .
exit /b 1
