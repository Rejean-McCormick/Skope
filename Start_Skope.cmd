@echo off
setlocal
set "SKOPE_HOME=%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
  echo [SKOPE] Python 3.12 not found: %PY%
  echo Install Python 3.12 or adjust PY in this launcher.
  pause
  exit /b 2
)
"%PY%" -c "import indexed_bzip2" >nul 2>&1
if errorlevel 1 (
  echo [SKOPE] indexed_bzip2 unavailable for Python 3.12.
  echo Check requirements before FULL WIKIDATA RECORDS extraction.
  echo Exploration can still run, but verified random access will be blocked.
)
pushd "%SKOPE_HOME%"
echo [SKOPE] Unified 1.0.0-rc.1 on http://127.0.0.1:8767
echo [SKOPE] Scope library: %SKOPE_HOME%scopes
echo [SKOPE] Wikidata SQLite is read-only. D: evidence stays where it is.
"%PY%" -u -m skope serve --db "D:\EncyKlopedia\30_working\wikidata\wikidata.compact.sqlite" %*
set "STATUS=%ERRORLEVEL%"
popd
if not "%STATUS%"=="0" pause
exit /b %STATUS%
