param([string]$SourceText)
$ErrorActionPreference='Stop'
$tokens=$null;$errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseInput($SourceText,[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors | Out-String)}
foreach($name in @('Resolve-FurMarkVulkanDevice','Get-FurMarkFailureDetail','Get-FurMarkLaunchText','Get-FurMarkGlEnvironment','Copy-FurMarkDiagnosticLogs','Confirm-FurMarkWorkloadRenderer','Write-GpuErrorDiagnostic','Set-GpuFailureRecord','Stop-GpuWorkflow','Assert-GpuWorkload')){
 $node=$ast.Find({param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$true)
 if($node){Invoke-Expression $node.Extent.Text}
}
function Log($message){$script:Logs+= $message}
$script:Logs=@()
$script:GpuTestStart=[datetime]'2026-10-09T00:04:41.0062579'
$script:GpuTestEnd=[datetime]'2026-10-09T11:17:32'
$script:GpuTestReason='';$script:GpuActualSeconds=0
# Failure recording must not depend on a cmdlet that can itself throw.
function New-TimeSpan {throw 'simulated duration cmdlet failure'}
try{Stop-GpuWorkflow 'original load failure' $script:GpuTestEnd}
catch{if($_.Exception.Message -notlike '*original load failure*'){throw 'Original GPU failure was replaced by recording exception'}}
if($script:GpuActualSeconds -ne 40371 -or $script:GpuTestReason -notlike '*original load failure*'){throw 'Failure duration/reason absent'}
if(@($script:Logs | Where-Object {$_ -like '[[]GPU FAIL[]]*'}).Count -ne 1){throw 'GPU failure log missing'}

# Process inspection errors retain the original exception before wrapper/cleanup.
function Get-Date {[datetime]'2026-10-09T11:17:32'}
$script:Logs=@()
$p=[pscustomobject]@{Id=17888}
$p | Add-Member ScriptMethod Refresh {throw [InvalidOperationException]::new('original refresh error')}
try{Assert-GpuWorkload @($p) $false}catch{}
if(($script:Logs -join "`n") -notlike '*original refresh error*Stack=*' -or $script:GpuTestReason -notlike '*original refresh error*' -or $script:GpuActualSeconds -ne 40371){throw 'Inspection error/duration lost'}
Remove-Item Function:Get-Date

# A duration conversion error preserves the reason and explicitly marks unknown duration.
$script:GpuTestStart='invalid timestamp'
try{Stop-GpuWorkflow 'original failure with invalid start' $script:GpuTestEnd}catch{}
if($script:GpuTestReason -notlike '*original failure with invalid start*' -or $script:GpuTestReason -notlike '*实际时长无法计算*' -or $null -ne $script:GpuActualSeconds){throw 'Invalid duration concealed the failure'}
$script:GpuTestStart=[datetime]'2026-10-09T00:04:41.0062579'

# Replay the real main workflow catch with a partial failure record.
# No hardware commands or pressure tools are executed.
$workflow=@($ast.EndBlock.Statements | Where-Object {
 $_ -is [System.Management.Automation.Language.TryStatementAst] -and $_.Finally.Extent.Text -like '*Build-Report*'
})
function Initialize-StressToolPreparation {}
function Stage-Message($message){}
function Run-Phase($phase,$seconds,$gpu,$cpu,$disk){
 $script:Phases+=$phase
 $script:WorkflowGpuFailed=$true;$script:GpuTestStatus='FAIL'
 throw [InvalidOperationException]::new('original inspection exception')
}
function Merge-BaseReportNonDiskSamples {}
function Build-Report {
 if($script:GpuTestReason -notlike '*original inspection exception*' -or $script:GpuActualSeconds -ne 40371){throw 'Partial failure state reached report without repair'}
}
function Copy-FurMarkDiagnosticLogs {}
function Write-Zip {}
$Mode='staged';$AllHours=0;$FastScanOnly=$false;$GpuMinutes=723
$HtmlReport='mock.html';$ZipPath='mock.zip'
$script:WorkflowGpuFailed=$false;$script:GpuTestReason='';$script:GpuActualSeconds=0
$script:Logs=@();$script:Phases=@()
Invoke-Expression $workflow[0].Extent.Text
if(($script:Phases -join ',') -ne 'gpu'){throw 'Later stages executed after GPU failure'}
$diagnostic=$script:Logs -join "`n"
foreach($text in @('original inspection exception','System.InvalidOperationException','ErrorId=','Position=','Stack=')){
 if(!$diagnostic.Contains($text)){throw "Missing original diagnostic: $text"}
}

# Already recorded failures keep their original end time and reason.
$script:GpuTestReason='original established failure';$script:GpuActualSeconds=40371
$script:Logs=@();$script:Phases=@()
function Build-Report {
 if($script:GpuTestReason -ne 'original established failure' -or $script:GpuActualSeconds -ne 40371){throw 'Existing failure record overwritten'}
}
Invoke-Expression $workflow[0].Extent.Text

# Non-GPU exceptions continue to propagate, with the existing report finally.
function Run-Phase { $script:WorkflowGpuFailed=$false;throw 'unrelated workflow exception' }
function Build-Report {}
try{Invoke-Expression $workflow[0].Extent.Text;throw 'Expected unrelated error'}
catch{if($_.Exception.Message -notlike '*unrelated workflow exception*'){throw}}
'PASS: original exception/stack, partial failure recovery, long duration and unchanged abort behavior'
