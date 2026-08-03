@echo off
REM ClaudeChat Windows launcher — add this scripts\ folder to your user PATH.
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"

if not defined CLAUDE_HOME set "CLAUDE_HOME=%ROOT%"
cd /d "%CLAUDE_HOME%" 2>nul
if errorlevel 1 (
  echo Error: CLAUDE_HOME is invalid: %CLAUDE_HOME%
  exit /b 1
)

if exist "%CLAUDE_HOME%\.venv\Scripts\python.exe" (
  "%CLAUDE_HOME%\.venv\Scripts\python.exe" -m claudechat %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python -m claudechat %*
  exit /b %ERRORLEVEL%
)

echo Error: Python not found. Create a venv in the project and install deps:
echo   cd "%CLAUDE_HOME%"
echo   python -m venv .venv
echo   .venv\Scripts\activate
echo   pip install -r requirements.txt
echo   pip install -e .
exit /b 1
