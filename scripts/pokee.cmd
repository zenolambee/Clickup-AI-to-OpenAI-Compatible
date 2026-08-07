@echo off
REM PokeeChat Windows launcher — add this scripts\ folder to your user PATH.
REM Works from any directory. Example:
REM   pokee serve
REM   pokee setup
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
REM Resolve project root (parent of scripts\)
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"

if not defined POKEECHAT_HOME set "POKEECHAT_HOME=%ROOT%"
cd /d "%POKEECHAT_HOME%" 2>nul
if errorlevel 1 (
  echo Error: POKEECHAT_HOME is invalid: %POKEECHAT_HOME%
  exit /b 1
)

if exist "%POKEECHAT_HOME%\.venv\Scripts\python.exe" (
  "%POKEECHAT_HOME%\.venv\Scripts\python.exe" -m pokeechat %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python -m pokeechat %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 -m pokeechat %*
  exit /b %ERRORLEVEL%
)

echo Error: Python not found. Create a venv in the project and install deps:
echo   cd "%POKEECHAT_HOME%"
echo   python -m venv .venv
echo   .venv\Scripts\activate
echo   pip install -r requirements.txt
echo   pip install -e .
exit /b 1