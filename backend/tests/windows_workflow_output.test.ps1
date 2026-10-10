param([string]$ScriptPath,[string]$SourceText)
$ErrorActionPreference='Stop'
if(!$SourceText){
 if(!$ScriptPath){$ScriptPath=Join-Path $PSScriptRoot '../scripts/windows/v104_windows_stress.ps1'}
 $SourceText=[IO.File]::ReadAllText($ScriptPath)
}
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseInput($SourceText,[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors | Out-String)}
$workflow=@($ast.EndBlock.Statements | Where-Object {
 $_ -is [System.Management.Automation.Language.TryStatementAst] -and $_.Finally.Extent.Text -like '*Build-Report*'
})
if($workflow.Count -ne 1){throw 'Expected exactly one main workflow'}
function Stage-Message($message){$script:Stages+= $message}
function Log($message){$script:Logs+= $message}
function Initialize-StressToolPreparation {}
function Run-Phase($phase,$seconds,$gpu,$cpu,$disk){
 $script:Phases+= $phase
 if($phase -eq 'gpu' -and $script:FailGpu){$script:WorkflowGpuFailed=$true;throw 'simulated GPU failure'}
}
function Get-DiskBothSplitDurations($seconds){[pscustomobject]@{StabilitySeconds=90;ThroughputSeconds=90;Policy='split'}}
function Invoke-DiskThroughputProbeIfNeeded {}
function Merge-BaseReportNonDiskSamples {$script:ReportSteps+='merge'}
function Build-Report {$script:ReportSteps+='html'}
function Write-Zip {$script:ReportSteps+='zip'}
$Mode='staged';$AllHours=0;$FastScanOnly=$false
$GpuMinutes=3;$CpuMinutes=3;$DiskMinutes=3;$DiskIoProfile='both'
$HtmlReport='mock-report.html';$ZipPath='mock-report.zip'
foreach($fail in @($false,$true)){
 $script:FailGpu=$fail;$script:WorkflowGpuFailed=$false
 $script:Stages=@();$script:Logs=@();$script:Phases=@();$script:ReportSteps=@()
 Invoke-Expression $workflow[0].Extent.Text
 if(($script:ReportSteps -join ',') -ne 'merge,html,zip'){throw 'Report generation order incorrect'}
 if(($script:Logs | Where-Object {$_ -like "*$HtmlReport*"}).Count -ne 1){throw 'HTML path log missing'}
 if(($script:Logs | Where-Object {$_ -like "*$ZipPath*"}).Count -ne 1){throw 'ZIP path log missing'}
 if($script:Logs -notcontains '[RUN] Starting selected stress workload...'){throw 'Start log missing'}
 if($fail){
  if(($script:Phases -join ',') -ne 'gpu'){throw 'Failure did not abort later phases'}
  if($script:Stages[-1] -notlike '*GPU*'){throw 'GPU failure completion message missing'}
 } else {
  if(($script:Phases -join ',') -ne 'gpu,cpu,disk'){throw 'Normal sequential workflow incomplete'}
  if($script:Stages[-1] -notlike '*所有测试完成*'){throw 'Normal completion message missing'}
 }
}
$function=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq 'Start-FurMarkStress'},$true)
Invoke-Expression $function.Extent.Text
function Has-NvidiaGpu {$false}
$script:Stages=@();$script:Logs=@()
$result=@(Start-FurMarkStress 180)
if($result.Count -ne 0 -or !$script:GpuSkipImmediate -or $script:GpuTestStatus -ne 'Not Tested'){throw 'GPU skip failed'}
if($script:Logs.Count -ne 1 -or $script:Stages.Count -ne 1){throw 'GPU skip output missing'}
'PASS: actual workflow output for completion, GPU failure and no-GPU skip; report/ZIP path logs'
