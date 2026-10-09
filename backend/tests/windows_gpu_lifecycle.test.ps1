param([string]$ScriptPath, [string]$SourceText)
$ErrorActionPreference = 'Stop'
if(!$SourceText){
 if(!$ScriptPath){$ScriptPath=Join-Path $PSScriptRoot '../scripts/windows/v105_windows_stress.ps1'}
 $SourceText=[IO.File]::ReadAllText($ScriptPath)
}
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseInput($SourceText,[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors | Out-String)}
foreach($name in @('Write-GpuErrorDiagnostic','Set-GpuFailureRecord','Assert-GpuWorkload','Stop-GpuWorkflow','Run-Phase')){
 $node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
 if(!$node){throw "Missing function: $name"}
 Invoke-Expression $node.Extent.Text
}
function Log($message) { $script:Messages += $message }
function Get-GpuWorkloadUtilization { $script:GpuLastUtilization }
function Stage-Message($message) {}
function Stop-Procs($processes) { $script:Stopped=$true }
function New-TestProcess($exited,$code=0) {
 $p=[pscustomobject]@{Id=123;HasExited=$exited;ExitCode=$code;ExitTime=(Get-Date)}
 $p | Add-Member ScriptMethod Refresh {}
 return $p
}
function Reset-Test {
 $script:Messages=@();$script:Stopped=$false;$script:WorkflowGpuFailed=$false
 $script:GpuTestStatus='Running';$script:GpuTestStart=Get-Date
 $script:GpuPlannedEnd=$script:GpuTestStart.AddSeconds(720);$script:GpuProcessExitTime=$null
 $script:GpuLoadEstablished=$false;$script:GpuLowLoadSince=$null
 $script:GpuLoadCheckStartedAt=(Get-Date).AddSeconds(-200)
 $script:GpuLastUtilization=100
 $script:GpuPreparationTimeoutSeconds=120;$script:GpuLoadLossSeconds=120
}
function Expect-Failure($p,$text) {
 try { Assert-GpuWorkload @($p) $false; throw 'Expected GPU failure' }
 catch { if($_.Exception.Message -notlike "*$text*"){throw} }
 if(!$script:WorkflowGpuFailed -or $script:GpuTestStatus -ne 'FAIL'){throw 'Failure state missing'}
}
Reset-Test
Expect-Failure (New-TestProcess $true -1073741819) 'ExitCode=-1073741819'
Reset-Test
Expect-Failure (New-TestProcess $true 0) 'ExitCode=0'
Reset-Test
Assert-GpuWorkload @((New-TestProcess $false)) $false
if(!$script:GpuLoadEstablished){throw 'Healthy GPU not accepted'}
$script:GpuLastUtilization=0
Assert-GpuWorkload @((New-TestProcess $false)) $false
$script:GpuLowLoadSince=(Get-Date).AddSeconds(-121)
Expect-Failure (New-TestProcess $false) 'GPU load lost'
Reset-Test
$script:GpuLastUtilization=$null
Expect-Failure (New-TestProcess $false) 'GPU load not established'
Reset-Test
$script:GpuLoadEstablished=$true;$script:GpuLowLoadSince=(Get-Date).AddSeconds(-121)
Assert-GpuWorkload @((New-TestProcess $false)) $false
if($null -ne $script:GpuLowLoadSince){throw 'Recovered load did not clear timer'}
Reset-Test
# A naturally timed exit is allowed only at the planned boundary after load validation.
$script:GpuLoadEstablished=$true
$script:GpuPlannedEnd=Get-Date
Assert-GpuWorkload @((New-TestProcess $true)) $true
Reset-Test
function Start-FurMarkStress($seconds) { New-TestProcess $true 7 }
function Start-Sleep {}
function Write-MonitorSample($phase) { $script:GpuLastUtilization=100 }
$script:LaterPhaseStarted=$false
try {
 Run-Phase 'gpu' 720 $true $false $false
 $script:LaterPhaseStarted=$true
} catch { if($_.Exception.Message -notlike '*ExitCode=7*'){throw} }
if($script:LaterPhaseStarted -or !$script:Stopped){throw 'Workflow did not abort and clean up'}
Reset-Test
$script:RefreshCount=0
function Start-FurMarkStress($seconds) {
 $p=New-TestProcess $false
 $p | Add-Member ScriptMethod Refresh {
  $script:RefreshCount++
  if($script:RefreshCount -ge 2){$this.HasExited=$true;$this.ExitCode=9}
 } -Force
 return $p
}
$script:LaterPhaseStarted=$false
try { Run-Phase 'gpu' 720 $true $false $false; $script:LaterPhaseStarted=$true }
catch { if($_.Exception.Message -notlike '*ExitCode=9*'){throw} }
if($script:LaterPhaseStarted -or !$script:Stopped){throw 'Mid-test exit did not stop the workflow'}
'PASS: GPU lifecycle, load loss/recovery, exit codes, sequential abort and cleanup'

# Replay the v102 report: FurMark starts at :52, script monitoring at :55,
# process exits after its full 180 seconds, and polling detects exit at :53.
Reset-Test
$script:FakeNow=[datetime]'2026-10-08 23:11:53'
function Get-Date { $script:FakeNow }
$script:GpuTestStart=[datetime]'2026-10-08 23:08:52'
$script:GpuPlannedEnd=$script:GpuTestStart.AddSeconds(180)
$script:GpuLoadEstablished=$true
$script:GpuLastUtilization=0
$p=New-TestProcess $true 0
$p | Add-Member NoteProperty ExitTime ([datetime]'2026-10-08 23:11:52') -Force
Assert-GpuWorkload @($p) $false
if($script:WorkflowGpuFailed -or $null -ne $script:GpuLowLoadSince){throw 'Normal timed exit misclassified'}
# Late polling must not conceal an exit before the configured deadline.
Reset-Test
$script:GpuTestStart=[datetime]'2026-10-08 23:08:52'
$script:GpuPlannedEnd=$script:GpuTestStart.AddSeconds(180)
$script:GpuLoadEstablished=$true
$p=New-TestProcess $true 0
$p | Add-Member NoteProperty ExitTime ([datetime]'2026-10-08 23:11:20') -Force
Expect-Failure $p 'ExitCode=0'
# The same rules apply to 12 hours; delayed polling cannot extend a failed run.
foreach($seconds in @(180,43200)){
 Reset-Test
 $script:GpuTestStart=[datetime]'2026-10-08 11:01:47'
 $script:GpuPlannedEnd=$script:GpuTestStart.AddSeconds($seconds)
 $script:FakeNow=$script:GpuPlannedEnd.AddSeconds(300)
 $script:GpuLoadEstablished=$true
 $p=New-TestProcess $true 0
 $p.ExitTime=$script:GpuPlannedEnd
 Assert-GpuWorkload @($p) $false
 $p.ExitTime=$script:GpuPlannedEnd.AddSeconds(-50)
 Expect-Failure $p 'ExitCode=0'
 Reset-Test
 $script:GpuPlannedEnd=$script:FakeNow
 $script:GpuLoadEstablished=$true
 Expect-Failure (New-TestProcess $true 9) 'ExitCode=9'
}
# At the deadline, verify the actual exit instead of force-stopping and assuming PASS.
Reset-Test
$script:GpuPlannedEnd=$script:FakeNow
$script:GpuLoadEstablished=$true
$p=New-TestProcess $false
$p | Add-Member ScriptMethod WaitForExit { param($milliseconds) $this.HasExited=$true;$this.ExitCode=0;$this.ExitTime=$script:GpuPlannedEnd.AddSeconds(2);return $true }
Assert-GpuWorkload @($p) $true
Reset-Test
$script:GpuPlannedEnd=$script:FakeNow
$script:GpuLoadEstablished=$true
$p=New-TestProcess $false
$p | Add-Member ScriptMethod WaitForExit { param($milliseconds) $this.HasExited=$true;$this.ExitCode=9;return $true }
try { Assert-GpuWorkload @($p) $true; throw 'Expected nonzero exit failure' }
catch {if($_.Exception.Message -notlike '*ExitCode=9*'){throw}}
Reset-Test
$script:GpuPlannedEnd=$script:FakeNow
$script:GpuLoadEstablished=$true
$p=New-TestProcess $false
$p | Add-Member ScriptMethod WaitForExit { param($milliseconds) return $false }
try { Assert-GpuWorkload @($p) $true; throw 'Expected completion timeout' }
catch {if($_.Exception.Message -notlike '*did not exit within 30s*'){throw}}
# Run the complete sequential GPU phase with native deadline, launch wait and
# simulated slow monitor calls. A healthy phase must permit the next stage.
foreach($seconds in @(180,43200)){
 $script:FakeNow=[datetime]'2026-10-08 11:01:47'
 Reset-Test
 function Start-FurMarkStress($duration){
  $script:GpuTestStart=$script:FakeNow
  $p=New-TestProcess $false
  $p | Add-Member ScriptMethod Refresh {
   if($script:FakeNow -ge $script:GpuPlannedEnd){
    $this.HasExited=$true;$this.ExitTime=$script:GpuPlannedEnd;$this.ExitCode=0
   }
  } -Force
  return $p
 }
 function Start-Sleep($Seconds){$script:FakeNow=$script:FakeNow.AddSeconds($Seconds)}
 function Write-MonitorSample($Phase){$script:FakeNow=$script:FakeNow.AddSeconds(6)}
 function Get-GpuWorkloadUtilization { 100 }
 $script:LaterPhaseStarted=$false
 Run-Phase 'gpu' $seconds $true $false $false
 $script:LaterPhaseStarted=$true
 if($script:WorkflowGpuFailed -or $script:GpuTestStatus -ne 'PASS' -or !$script:LaterPhaseStarted -or $script:GpuActualSeconds -ne $seconds){
  throw "Healthy ${seconds}s phase failed or timing drifted"
 }
}
Remove-Item Function:Get-Date
'PASS: real-world startup offset and late-polling exit boundary'

# Exercise the real HTML/summary builder with valid historical GPU samples.
# Hardware commands and file I/O are mocked; no hardware workload is started.
foreach($parameter in $ast.ParamBlock.Parameters){
 if($parameter.DefaultValue){ Set-Variable -Name $parameter.Name.VariablePath.UserPath -Value (Invoke-Expression $parameter.DefaultValue.Extent.Text) }
}
foreach($node in $ast.FindAll({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst]},$true)){
 Invoke-Expression $node.Extent.Text
}
function Log($message) {}
function Get-CimInstance { throw 'Hardware disabled in test' }
function nvidia-smi { '0, NVIDIA RTX test, 1, 70, 80, 450, 600, 24000' }
function New-SvgChart {}
function Test-Path($Path) { $Path -eq $MonitorCsv }
function Import-Csv($Path) {
 if($Path -eq $MonitorCsv){
  @'
Timestamp,Phase,GPU_Count,GPU_Util_Max_Percent,GPU_Temp_Max_C,GPU_Fan_Max_Percent,GPU_Power_Total_W,GPU_Mem_Used_Total_MB
2026-10-08 11:01:50,gpu,1,100,70,80,450,600
2026-10-08 22:13:13,gpu,1,100,71,80,450,600
'@ | ConvertFrom-Csv
 }
}
$script:Outputs=@{}
function Out-File {
 param([Parameter(ValueFromPipeline=$true)]$InputObject,[Parameter(Position=0)]$FilePath,$Encoding)
 process { $script:Outputs[$FilePath] += [string]$InputObject }
}
$LogDir='C:\mock';$ChartDir='C:\mock';$ReportRoot='C:\mock'
$MonitorCsv='C:\mock\monitor.csv';$DiskDriveIoCsv='C:\mock\disk.csv'
$HtmlReport='C:\mock\report.html';$SummaryTxt='C:\mock\summary.txt';$ZipPath='C:\mock\report.zip'
$StartTime=Get-Date;$ScriptBuild='v105'
$script:ResolvedTestDrives=@();$script:DiskDriveProfiles=@{};$script:ToolInfo=@()
$script:GpuPowerLimitW=450;$script:WorkflowGpuFailed=$true;$script:OfflineRebuildMode=$false
$script:GpuTestReason='FurMark exited; ExitCode=7; reason unknown'
$script:GpuActualSeconds=40300;$script:GpuTestStatus='FAIL'
$script:CpuModuleAttempted=$false;$script:DiskModuleAttempted=$false
Build-Report
if($script:Outputs[$SummaryTxt] -notlike 'Overall=FAIL*'){throw 'GPU failure masked by sampled load'}
if($script:Outputs[$HtmlReport] -notlike '*ExitCode=7*'){throw 'Failure reason absent from HTML'}
$gpu=@($script:StatusItems | Where-Object { $_.Status -eq 'FAIL' -and $_.Participate })
if($gpu.Count -ne 1){throw 'Unexecuted stages incorrectly failed'}
if(@($script:StatusItems | Where-Object { $_.Status -eq 'NOT_TESTED' }).Count -lt 3){throw 'Later stages not marked untested'}
# The recovered record must also survive the actual customer HTML/summary builder.
$script:GpuTestStart=[datetime]'2026-10-09T00:04:41.0062579'
Set-GpuFailureRecord 'original handler error' ([datetime]'2026-10-09T11:17:32')
$script:Outputs=@{}
Build-Report
if($script:Outputs[$HtmlReport] -notlike '*original handler error*' -or $script:Outputs[$HtmlReport] -notlike '*40371*'){throw 'Recovered reason/duration absent from real HTML'}
if($script:Outputs[$SummaryTxt] -notlike 'Overall=FAIL*'){throw 'Recovered GPU failure changed overall status'}
$script:GpuTestReason='FurMark exited; ExitCode=7; reason unknown'
'PASS: real report builder preserves GPU failure and excludes unexecuted stages'

# Failed launch has no samples but still must fail the GPU and overall report.
function Import-Csv($Path) { @() }
$script:Outputs=@{}
Build-Report
if($script:Outputs[$SummaryTxt] -notlike 'Overall=FAIL*'){throw 'Failed launch masked by missing samples'}
if($script:Outputs[$HtmlReport] -notlike '*ExitCode=7*'){throw 'Launch failure reason absent'}
'PASS: report builder handles failed launch without samples'
