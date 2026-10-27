@echo off
setlocal
set "ROOT=%~dp0"
set "PY=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not exist "%PY%" (
 echo [ERROR] Python 3.12 introuvable. Installation requise.
 pause
 exit /b 2
)
if not exist "%ROOT%encyk\run_manager.pyw" (
 echo [ERROR] Module EncyK absent.
 pause
 exit /b 2
)
rem Require explicit, preconfigured D: junctions. Prevent EncyK manager
rem from quietly creating evidence or index folders inside the code checkout.
"%PY%" -c "import pathlib,sys; r=pathlib.Path(sys.argv[1]); links=['20_evidence','30_working','90_runtime','10_sources/wikidata/dumps','10_sources/lexical']; sys.exit(0 if all((r/p).is_junction() for p in links) else 3)" "%ROOT%encyk"
if errorlevel 1 (
 echo [REFUSED] EncyK data junctions are not all configured.
 echo First preview, then explicitly apply with PowerShell 7:
 echo   pwsh -File "%ROOT%encyk\configure_data_on_D.ps1"
 echo   pwsh -File "%ROOT%encyk\configure_data_on_D.ps1" -Apply
 echo This is a code-only candidate. No D: changes are made automatically.
 pause
 exit /b 3
)
cd /d "%ROOT%encyk"
"%PY%" -B "%ROOT%encyk\run_manager.pyw"
if errorlevel 1 pause
