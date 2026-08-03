@echo off
REM GeminiChat Windows launcher — add this scripts\ folder to your user PATH.
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"

if not defined GEMINICHAT_HOME set "GEMINICHAT_HOME=%ROOT%"
cd /d "%GEMINICHAT_HOME%" 2>nul
if errorlevel 1 (
  echo Error: GEMINICHAT_HOME is invalid: %GEMINICHAT_HOME%
  exit /b 1
)

if exist "%GEMINICHAT_HOME%\.venv\Scripts\python.exe" (
  "%GEMINICHAT_HOME%\.venv\Scripts\python.exe" -m geminichat %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python -m geminichat %*
  exit /b %ERRORLEVEL%
)

echo Error: Python not found. Create a venv in the project and install deps:
echo   cd "%GEMINICHAT_HOME%"
echo   python -m venv .venv
echo   .venv\Scripts\activate
echo   pip install -r requirements.txt
echo   pip install -e .
exit /b 1
