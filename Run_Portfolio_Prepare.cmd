@echo off
setlocal
set "SKOPE_HOME=%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
 echo Python 3.12 is required at %PY%
 pause
 exit /b 2
)
if "%~1"=="" (
 echo Usage: Run_Portfolio_Prepare.cmd "C:\path\to\Kristals-v11.zip"
 echo This generates a RESEARCH worklist, NOT published Kristals.
 pause
 exit /b 2
)
set "INPUT=%~1"
set "WORK=%SKOPE_HOME%portfolio-work"
set "DB=D:\EncyKlopedia\30_working\wikidata\wikidata.compact.sqlite"
if not exist "%DB%" (
 echo Existing Wikidata index not found: %DB%
 echo Update DB in this script to match your installation.
 pause
 exit /b 2
)
pushd "%SKOPE_HOME%"
"%PY%" -m skope portfolio prepare --input "%INPUT%" --work "%WORK%" --db "%DB%" --review-out "%WORK%\review-candidates.csv" --max-queries 25000 --suggest-draft
set "RESULT=%ERRORLEVEL%"
if "%RESULT%"=="0" echo Results: %WORK%\review-candidates.csv
popd
pause
exit /b %RESULT%
