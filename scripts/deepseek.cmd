@echo off
REM DeepSeekChat Windows launcher — add this scripts\ folder to your user PATH.
REM Works from any directory. Example:
REM   deepseek serve
REM   deepseek setup
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
REM Resolve project root (parent of scripts\)
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"

if not defined DEEPSEEKCHAT_HOME set "DEEPSEEKCHAT_HOME=%ROOT%"
cd /d "%DEEPSEEKCHAT_HOME%" 2>nul
if errorlevel 1 (
  echo Error: DEEPSEEKCHAT_HOME is invalid: %DEEPSEEKCHAT_HOME%
  exit /b 1
)

if exist "%DEEPSEEKCHAT_HOME%\.venv\Scripts\python.exe" (
  "%DEEPSEEKCHAT_HOME%\.venv\Scripts\python.exe" -m deepseekchat %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python -m deepseekchat %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 -m deepseekchat %*
  exit /b %ERRORLEVEL%
)

echo Error: Python not found. Create a venv in the project and install deps:
echo   cd "%DEEPSEEKCHAT_HOME%"
echo   python -m venv .venv
echo   .venv\Scripts\activate
echo   pip install -r requirements.txt
echo   pip install -e .
exit /b 1