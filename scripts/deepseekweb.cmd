@echo off
REM DeepSeekWeb Windows launcher (chat.deepseek.com cookie).
REM   deepseekweb serve
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "ROOT=%%~fI"
if not defined DEEPSEEKWEB_HOME set "DEEPSEEKWEB_HOME=%ROOT%"
cd /d "%DEEPSEEKWEB_HOME%" 2>nul
if errorlevel 1 (
  echo Error: DEEPSEEKWEB_HOME is invalid: %DEEPSEEKWEB_HOME%
  exit /b 1
)
if exist "%DEEPSEEKWEB_HOME%\.venv\Scripts\python.exe" (
  "%DEEPSEEKWEB_HOME%\.venv\Scripts\python.exe" -m deepseekweb %*
  exit /b %ERRORLEVEL%
)
where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python -m deepseekweb %*
  exit /b %ERRORLEVEL%
)
echo Error: Python not found. Create a venv and install deps. >&2
exit /b 1