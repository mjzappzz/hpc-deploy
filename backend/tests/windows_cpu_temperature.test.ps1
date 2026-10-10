param([string]$ScriptPath = (Join-Path $PSScriptRoot '../scripts/windows/v104_windows_stress.ps1'), [string]$SourceText)
$ErrorActionPreference = 'Stop'
$tokens = $null; $parseErrors = $null
if (!$SourceText) { $SourceText = [IO.File]::ReadAllText($ScriptPath) }
$ast = [System.Management.Automation.Language.Parser]::ParseInput($SourceText, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
foreach ($name in @('Get-IpmiCpuTemperatureSensors', 'Select-CpuTemperatureFromSensors', 'Get-CpuTelemetrySample')) {
    $definition = $ast.Find({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $name }, $true)
    if (!$definition -and $name -eq "Get-IpmiCpuTemperatureSensors") { continue }
    if (!$definition) { throw "Missing function: $name" }
    Invoke-Expression $definition.Extent.Text
}
function Sensor($name, $value, $hardware = 'Board / IPMI', $type = 'Motherboard') {
    [pscustomobject]@{ Name=$name; Value=$value; Hardware=$hardware; HardwareType=$type; HardwareId='/test'; SensorType='Temperature' }
}
function Assert-Selection($sensors, $expected, $source) {
    $actual = Select-CpuTemperatureFromSensors @($sensors)
    if ($actual -ne $expected -or $script:CpuTempSensorName -notlike "*$source*") {
        throw "Expected $expected from $source; got $actual from $script:CpuTempSensorName"
    }
}
$PreferIpmiCpuTemp = $true; $UseCpuLikeTemperatureFallback = $true
$lhm = Sensor 'Core (Tctl/Tdie)' 123.2 'AMD EPYC 7B13' 'Cpu'
Assert-Selection @((Sensor 'CPU0_TEMP' 37), (Sensor 'CPU0_DTS' 63), $lhm) 37 'CPU0_TEMP'
Assert-Selection @((Sensor 'CPU0_DTS' 66), $lhm) 123.2 'Tctl/Tdie'
Assert-Selection @((Sensor 'CPU0_TEMP' 37), (Sensor 'CPU1_TEMP' 70), $lhm) 70 'CPU1_TEMP'
foreach ($name in @('CPU_TEMP_01', 'CPU_TEMP_02', 'CPU TEMP 1', 'CPU-TEMP-02')) {
    Assert-Selection @((Sensor $name 45), $lhm) 45 $name
}
Assert-Selection @((Sensor 'CPU_AREA_TEMP' 41), $lhm) 41 'CPU_AREA_TEMP'
Assert-Selection @((Sensor 'CPU0_TEMP' 20 'GPU board' 'GpuNvidia'), $lhm) 123.2 'Tctl/Tdie'
Assert-Selection @($lhm) 123.2 'Tctl/Tdie'
if ($null -ne (Select-CpuTemperatureFromSensors @((Sensor 'CPU0_DTS' 66)))) { throw 'DTS entered CPU-like fallback' }
$PreferIpmiCpuTemp = $false
Assert-Selection @((Sensor 'CPU0_TEMP' 37), $lhm) 123.2 'Tctl/Tdie'
$PreferIpmiCpuTemp = $true
$EnableCpuTemperature = $true; $EnableCpuPower = $false; $script:LhmReady = $true
function Get-LhmTelemetrySensors { @((Sensor 'CPU0_TEMP' 37), (Sensor 'CPU0_DTS' 63 'Board, model / IPMI'), $lhm) }
$sample = Get-CpuTelemetrySample
if ($sample.TempC -ne 37 -or $sample.TemperatureSensors.Count -ne 2) { throw 'TEMP/DTS telemetry missing or wrong selected value' }
if ($sample.TemperatureSensors[1].TempC -ne 63 -or $sample.TemperatureSensors[1].Sensor -notlike '*CPU0_DTS') { throw 'DTS source lost' }
# The legacy CSV schema must survive sensor names containing commas.
$rows = @($sample.TemperatureSensors | Select-Object @{Name='Timestamp';Expression={'2026-09-30 15:40:47'}}, Sensor, TempC | ConvertTo-Csv -NoTypeInformation | ConvertFrom-Csv)
if ($rows.Count -ne 2 -or $rows[0].TempC -ne '37') { throw 'CSV telemetry round trip failed' }
'PASS: PowerShell syntax and IPMI selection/telemetry regression cases'
