param(
  [ValidateSet('catholic-pilot','intellectuals','both')]
  [string]$Scope = 'catholic-pilot',
  [int]$PollSeconds = 120,
  [switch]$BuildQueryIndex,
  [switch]$PrepareFastAccess,
  [switch]$AllowFullScan
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script = Join-Path $Root '00_system\tools\scope-builder\scripts\run_scope_pipeline.py'
$Args = @('-u',$Script,'--root',$Root,'--wait-for-index','--poll-seconds',$PollSeconds,'--discovery-backend','index','--through','handoff')
if ($Scope -eq 'both') { $Args += @('--scope','catholic-pilot','--scope','intellectuals') }
else { $Args += @('--scope',$Scope) }
if ($BuildQueryIndex) { $Args += '--build-query-index' }
if ($PrepareFastAccess) { $Args += '--prepare-fast-access' }
if ($AllowFullScan) { $Args += '--allow-full-scan' }
& python @Args
exit $LASTEXITCODE
