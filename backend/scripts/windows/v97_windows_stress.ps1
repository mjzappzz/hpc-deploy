#requires -version 5.1
<#
NVIDIA GeForce / RTX FurMark2 + y-cruncher + DiskSpd Stability Report v97 CPU Telemetry Fix
Windows PowerShell 5.1+
ASCII-safe script body. Chinese text in HTML is encoded as HTML entities where needed.

V97 CPU telemetry corrections:
- Preserve v96 DiskSpd/report reliability corrections.
- Fix CPU temperature telemetry diagnostics and Ryzen/Zen sensor selection.
- Add CPU package power telemetry from LibreHardwareMonitor.
- Warm up LibreHardwareMonitor so package-power delta sensors have valid samples.
- Log CPU temperature/power sensor candidates and administrator privilege state.
- Add CPU power to monitor.csv, HTML summary, key metrics, and trend charts.
#>

param(
    [ValidateSet("gpu","cpu","disk","all","staged")]
    [string]$Mode = "staged",

    [double]$DurationHours = 1,

    [int]$GpuMinutes = 240,
    [int]$CpuMinutes = 240,
    [double]$DiskMinutes = 240,
    [double]$AllHours = 0,

    [int]$IntervalSeconds = 5,

    # v90: protect long stress tests from Windows Update reboot interruption
    [bool]$PauseWindowsUpdate = $true,
    [int]$WindowsUpdatePauseDays = 7,
    [bool]$EnableScreenshots = $false,
    [bool]$ManualFurMarkConfirm = $false,

    [string]$TestDrive = "E:",
    [string[]]$TestDrives = @(),
    [bool]$TestAllFixedDrives = $true,
    [string]$DiskFileSize = "100G",
    [ValidateSet("stability","throughput","both")]
    [string]$DiskIoProfile = "stability",
    [int]$DiskThroughputProbeSeconds = 120,
    [ValidateSet("append","split")]
    [string]$DiskBothTimePolicy = "split",
    [bool]$CleanupDiskSpdTempFiles = $true,
    [bool]$CleanupAllFixedDrives = $true,

    [string]$ToolRoot = "",
    [string]$ReportBase = "",
    [switch]$FastScanOnly,
    [string]$MergeBaseReportDir = "",

    [bool]$AutoDownloadDiskSpd = $true,
    [string]$DiskSpdUrl = "http://171.221.252.54:8573/chfs/shared/%E5%85%B6%E4%BB%96%E5%B8%B8%E7%94%A8%E8%BD%AF%E4%BB%B6%EF%BC%88%E5%90%AB%E5%8E%8B%E6%B5%8B%E8%84%9A%E6%9C%AC%E7%AD%89%EF%BC%89/Stress%E5%8E%8B%E6%B5%8B%E7%9B%B8%E5%85%B3%E8%84%9A%E6%9C%AC/windows%E5%8E%8B%E6%B5%8B/DiskSpd.ZIP",
    [string[]]$DiskSpdFallbackUrls = @("https://github.com/microsoft/diskspd/releases/latest/download/DiskSpd.zip","https://aka.ms/getdiskspd"),

    [bool]$UseOfficialFurMark2 = $true,
    [bool]$AutoDownloadFurMark2 = $true,
    [string]$FurMark2Url = "http://171.221.252.54:8573/chfs/shared/%E5%85%B6%E4%BB%96%E5%B8%B8%E7%94%A8%E8%BD%AF%E4%BB%B6%EF%BC%88%E5%90%AB%E5%8E%8B%E6%B5%8B%E8%84%9A%E6%9C%AC%E7%AD%89%EF%BC%89/Stress%E5%8E%8B%E6%B5%8B%E7%9B%B8%E5%85%B3%E8%84%9A%E6%9C%AC/windows%E5%8E%8B%E6%B5%8B/FurMark_2.10.2_win64.zip",
    [string[]]$FurMark2FallbackUrls = @(),

    [ValidateSet("ycruncher","prime95","custom")]
    [string]$CpuMemBackend = "ycruncher",
    [bool]$AutoDownloadYCruncher = $true,
    [string]$YCruncherUrl = "http://171.221.252.54:8573/chfs/shared/%E5%85%B6%E4%BB%96%E5%B8%B8%E7%94%A8%E8%BD%AF%E4%BB%B6%EF%BC%88%E5%90%AB%E5%8E%8B%E6%B5%8B%E8%84%9A%E6%9C%AC%E7%AD%89%EF%BC%89/Stress%E5%8E%8B%E6%B5%8B%E7%9B%B8%E5%85%B3%E8%84%9A%E6%9C%AC/windows%E5%8E%8B%E6%B5%8B/y-cruncher%20v0.8.7.9547b.zip",
    [string[]]$YCruncherFallbackUrls = @("https://www.numberworld.org/y-cruncher/y-cruncher%20v0.8.7.9547b.zip","https://www.numberworld.org/y-cruncher/y-cruncher%20v0.8.7.9547.zip"),

    [string]$FurMark2OfficialSource = "https://geeks3d.com/furmark/",
    [string]$YCruncherOfficialSource = "https://www.numberworld.org/y-cruncher/",
    [string]$DiskSpdOfficialSource = "https://github.com/microsoft/diskspd",

    [bool]$EnableCpuTemperature = $true,
    [bool]$EnableCpuPower = $true,
    [bool]$AutoDownloadLibreHardwareMonitor = $true,
    [string]$LibreHardwareMonitorUrl = "http://171.221.252.54:8573/chfs/shared/%E5%85%B6%E4%BB%96%E5%B8%B8%E7%94%A8%E8%BD%AF%E4%BB%B6%EF%BC%88%E5%90%AB%E5%8E%8B%E6%B5%8B%E8%84%9A%E6%9C%AC%E7%AD%89%EF%BC%89/Stress%E5%8E%8B%E6%B5%8B%E7%9B%B8%E5%85%B3%E8%84%9A%E6%9C%AC/windows%E5%8E%8B%E6%B5%8B/LibreHardwareMonitor.zip",
    [string[]]$LibreHardwareMonitorFallbackUrls = @("https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/releases/download/v0.9.6/LibreHardwareMonitor-net472.zip"),
    [string]$LibreHardwareMonitorOfficialSource = "https://github.com/LibreHardwareMonitor/LibreHardwareMonitor",
    [bool]$StartLibreHardwareMonitorGui = $true,
    [bool]$AutoConfirmPawIoInstall = $true,
    [int]$PawIoConfirmTimeoutSeconds = 90,
    [bool]$UseCpuLikeTemperatureFallback = $true,
    [bool]$PreferIpmiCpuTemp = $true,
    [int]$CpuTempPreInitSeconds = 12,

    # Thermal evaluation: avoid failing on short temperature spikes
    [int]$ThermalFailDurationSeconds = 30,

    [ValidateSet("auto","cuda","furmark")]
    [string]$GpuBackend = "auto",
    [int]$CudaMatrixSize = 8192,
    [ValidateRange(0,95)]
    [int]$GpuMemoryStressPercent = 0,
    [string]$FurMarkArgs = "",
    [bool]$FurMarkAutoEnter = $true,
    [int]$FurMarkAutoEnterDelaySeconds = 5,

    [string]$Prime95Args = "-t",
    [bool]$CpuBurner = $false,
    [int]$CpuBurnerLoadPercent = 75,

    [bool]$AutoFallbackCustomCpuMem = $true,
    [int]$CpuFallbackCheckSeconds = 20,
    [int]$CpuFallbackLoadThresholdPercent = 20,

    # y-cruncher CPU phase memory target (fixed policy)
    [int]$YCruncherMemoryPercent = 80,

    # fallback CPU+Memory worker settings
    [ValidateRange(1,128)]
    [int]$MemoryStressWorkers = 8,

    [int]$MemoryReserveGB = 16,

    [int]$CpuLoadPassPercent = 95,
    [int]$CpuAvgLoadPassPercent = 85,
    [int]$CpuAvgLoadWarnPercent = 70,
    [int]$CpuTempWarnC = 90,
    [int]$CpuTempFailC = 95,
    # Optional explicit official TDP override for CPU models not yet in the local catalog.
    [int]$CpuOfficialTdpW = 0,
    [int]$CpuClockWarnPercentOfMax = 50,
    [int]$MemoryLoadPassPercentOfTarget = 85,
    [int]$MemoryLoadFailPercentOfTarget = 70,
    [int]$MemoryUsageFailPercent = 95,
    [int]$GpuLoadPassPercent = 95,
    [int]$GpuAvgLoadPassPercent = 90,
    [int]$GpuTempWarnC = 85,
    [int]$GpuTempFailC = 95,
    [int]$GpuPowerPassW = 300,
    [int]$GpuFanHighPercent = 80,
    [int]$GpuFanFullPercent = 95,
    [int]$DiskThroughputPassMBps = 300,
    [int]$DiskThroughputFailMBps = 100,

    [bool]$LenientCustomerReport = $true,
    [int]$CpuStableSkipStartSeconds = 45,
    [int]$CpuStableSkipEndSeconds = 10,
    [int]$GpuStableSkipStartSeconds = 10,
    [int]$GpuStableSkipEndSeconds = 10,
    [int]$GpuEffectiveLoadMinPercent = 50,
    [int]$GpuEffectivePowerMinW = 100,
    [int]$DiskThroughputToleranceMBps = 25,

    [bool]$AutoHardwareThreshold = $true
)

# Thermal policy optimized: CPU/GPU temperature warning and fail thresholds adjusted for HPC workloads.
# Build/version identifiers (auto detected from script filename)
# Example: v90_windows_stress.ps1 -> ScriptBuild = v90
# Do not hardcode version here.
$ScriptFileName = [System.IO.Path]::GetFileNameWithoutExtension($MyInvocation.MyCommand.Name)
$ScriptBuildMatch = [regex]::Match($ScriptFileName, "v\d+")
if ($ScriptBuildMatch.Success) {
    $ScriptBuild = $ScriptBuildMatch.Value
}
else {
    $ScriptBuild = "unknown"
}

$YCruncherDisplayVersion = "auto"
$FurMarkDisplayVersion = "auto"
$DiskSpdDisplayVersion = "auto"

Write-Host ("[SCRIPT BUILD] {0} (from filename: {1})" -f $ScriptBuild,$ScriptFileName) -ForegroundColor Cyan

$ErrorActionPreference = "Continue"
# v58 path policy:
# - ReportBase controls where stress_report_yyyyMMdd_HHmmss and zip are created.
# - If ReportBase is not set, use the current working directory, not Desktop.
# - ToolRoot controls where FurMark2/y-cruncher/DiskSpd/LibreHardwareMonitor are stored.
# - If ToolRoot is not set, put stress_tools under ReportBase.
$StartTime = Get-Date
if ([string]::IsNullOrWhiteSpace($ReportBase)) {
    $ReportBase = (Get-Location).Path
}
$ReportBase = [System.IO.Path]::GetFullPath($ReportBase)
$Stamp = $StartTime.ToString("yyyyMMdd_HHmmss")
# v85: prefix report name with physical Windows LAN IPv4
# 排除 WSL / Docker / 虚拟网卡，优先获取 Ethernet/Wi-Fi 实际地址
try {
    $ReportIp = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object {
            $_.IPAddress -notlike "127.*" -and
            $_.IPAddress -notlike "169.254.*" -and
            $_.IPAddress -notlike "172.*" -and
            $_.IPAddress -notlike "192.168.56.*" -and
            $_.InterfaceAlias -notmatch "WSL|Hyper-V|Docker|VMware|VirtualBox|vEthernet"
        } |
        Sort-Object {
            if($_.InterfaceAlias -match "Ethernet|Wi-Fi|WLAN"){0}else{1}
        } |
        Select-Object -First 1 -ExpandProperty IPAddress
} catch { $ReportIp = $null }
if ([string]::IsNullOrWhiteSpace($ReportIp)) { $ReportIp = "unknown" }
$ReportPrefix = "${ReportIp}_stress_report_$Stamp"
$ReportRoot = Join-Path $ReportBase $ReportPrefix
$LogDir = Join-Path $ReportRoot "logs"
$ChartDir = Join-Path $ReportRoot "charts"
$ShotDir = Join-Path $ReportRoot "screenshots"
if ([string]::IsNullOrWhiteSpace($ToolRoot)) { $ToolRoot = Join-Path $ReportBase "stress_tools" }
$ToolRoot = [System.IO.Path]::GetFullPath($ToolRoot)
$LocalDiskSpdDir = Join-Path $ToolRoot "diskspd"
$LocalFurMark2Dir = Join-Path $ToolRoot "furmark2"
$LocalYCruncherDir = Join-Path $ToolRoot "ycruncher"
$LocalLibreHardwareMonitorDir = Join-Path $ToolRoot "librehardwaremonitor"
$LocalPawnIoDir = Join-Path $ToolRoot "pawnio"
$script:DiskSpdTempFiles = @()
New-Item -ItemType Directory -Force -Path $ReportRoot,$LogDir,$ChartDir,$ShotDir,$ToolRoot,$LocalDiskSpdDir,$LocalFurMark2Dir,$LocalYCruncherDir,$LocalLibreHardwareMonitorDir,$LocalPawnIoDir | Out-Null

$EventLog = Join-Path $LogDir "events.log"
$MonitorCsv = Join-Path $LogDir "monitor.csv"
$GpuSmiCsv = Join-Path $LogDir "gpu_smi.csv"
$CpuSensorCsv = Join-Path $LogDir "cpu_sensors.csv"
$SummaryTxt = Join-Path $ReportRoot "summary.txt"
$HtmlReport = Join-Path $ReportRoot "report.html"
$MemoryWorkerPs1 = Join-Path $ReportRoot "memory_worker.ps1"
$CpuBurnerPs1 = Join-Path $ReportRoot "cpu_burner.ps1"
$ZipPath = Join-Path (Split-Path $ReportRoot -Parent) ("{0}.zip" -f $ReportPrefix)
if (![string]::IsNullOrWhiteSpace($MergeBaseReportDir)) {
    try { $MergeBaseReportDir = [System.IO.Path]::GetFullPath($MergeBaseReportDir) } catch {}
    $script:MergeBaseReportDir = $MergeBaseReportDir
    $script:SupplementMergeMode = $true
} else {
    $script:MergeBaseReportDir = ""
    $script:SupplementMergeMode = $false
}
$script:CpuTempSensorName = ""
$script:CpuTempLast = $null
$script:CpuPowerSensorName = ""
$script:CpuPowerLast = $null
$script:CpuPowerLimitSensorName = ""
$script:CpuPowerLimitLast = $null
$script:CpuOfficialTdpW = $null
$script:CpuOfficialTdpSource = ""
$script:LhmReady = $false
$script:LhmComputer = $null
$script:LhmDiagDone = $false
$script:SkipDiskPhase = $false
$script:StatusItems = @()
$script:ResolvedTestDrives = @()
$script:DiskDriveProfiles = @{}
$script:DiskThresholdProfile = "Per-drive dynamic disk threshold"
$script:ToolInfo = @()
$script:GpuTestStatus = "Not Tested"
$script:GpuTestReason = ""
$script:GpuTestStart = $null
$script:GpuTestEnd = $null
$script:GpuActualSeconds = 0
$script:GpuSkipImmediate = $false
$script:GpuPowerLimitW = $null
$script:GpuThermalSlowdownC = $null
$script:GpuHardwareLimitSource = "Unavailable"

# Runtime CPU/Memory backend tracking for final report
$script:CpuMemBackendUsed = "NotStarted"
$script:CpuMemBackendReason = ""
$script:CpuMemMemoryPolicy = ""

# v95/v96: track whether each workload actually started.
# Selecting a module in Mode does not mean that the module was really tested.
$script:CpuModuleAttempted = $false
$script:CpuModuleExecuted = $false
$script:CpuModuleReason = "未启用"
$script:DiskModuleAttempted = $false
$script:DiskModuleExecuted = $false
$script:DiskModuleReason = "未启用"

function Log([string]$Msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Msg"
    Write-Host $line
    Add-Content -Path $EventLog -Value $line -Encoding UTF8
}



function Stage-Message([string]$Message) {
    Write-Host $Message -ForegroundColor Cyan
    Add-Content -Path $EventLog -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Message" -Encoding UTF8
}



# v90: pause Windows Update before long stress testing.
# 增加中文阶段提示，方便现场查看压测进度。
# This does not disable the Windows Update service; it only requests a temporary pause.
function Pause-WindowsUpdateForStress {
    if (!$PauseWindowsUpdate) {
        Log "[WINDOWS UPDATE] Pause disabled by parameter."
        return
    }

    try {
        $days = [Math]::Max(1, $WindowsUpdatePauseDays)
        Log "[WINDOWS UPDATE] Preparing pause request (${days} days)..."

        $key = "HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings"
        if (!(Test-Path $key)) {
            New-Item -Path $key -Force | Out-Null
        }

        $now = Get-Date
        $end = $now.AddDays($days)

        $startString = $now.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        $endString = $end.ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")

        New-ItemProperty -Path $key -Name "PauseQualityUpdatesStartTime" -Value $startString -PropertyType String -Force | Out-Null
        New-ItemProperty -Path $key -Name "PauseFeatureUpdatesStartTime" -Value $startString -PropertyType String -Force | Out-Null
        New-ItemProperty -Path $key -Name "PauseUpdatesStartTime" -Value $startString -PropertyType String -Force | Out-Null

        Log "[WINDOWS UPDATE] Pause requested until: $($end.ToString('yyyy-MM-dd HH:mm:ss'))"
        Write-Host "[准备完成] Windows更新暂停已开启，压测期间不会因系统更新自动重启。" -ForegroundColor Green
    }
    catch {
        Log "[WINDOWS UPDATE][WARN] Failed to pause updates: $($_.Exception.Message)"
    }
}
function Html([object]$v) { if ($null -eq $v) { return "" }; return [System.Net.WebUtility]::HtmlEncode([string]$v) }
function Num($v) { try { if ($null -eq $v -or [string]::IsNullOrWhiteSpace([string]$v)) { return $null }; return [double]$v } catch { return $null } }
function ToGB([double]$bytes) { return [math]::Round($bytes / 1GB, 2) }
function Convert-SizeToBytes([string]$SizeText) {
    if ($SizeText -match '^([0-9]+)([Gg])$') { return [int64]$matches[1] * 1GB }
    if ($SizeText -match '^([0-9]+)([Mm])$') { return [int64]$matches[1] * 1MB }
    if ($SizeText -match '^([0-9]+)([Kk])$') { return [int64]$matches[1] * 1KB }
    if ($SizeText -match '^([0-9]+)$') { return [int64]$matches[1] }
    return [int64](10GB)
}
function Add-ToolInfo($Module,$Tool,$Path,$Args,$Source) {
    $script:ToolInfo += [pscustomobject]@{Module=$Module;Tool=$Tool;Path=$Path;Args=$Args;Source=$Source}
}
function Add-Status($Item,$Status,$Reason,[bool]$Participate=$true) {
    $script:StatusItems += [pscustomobject]@{Item=$Item;Status=$Status;Reason=$Reason;Participate=$Participate}
}
function Get-Max($rows,$name) {
    $vals = @(); foreach ($r in $rows) { $x = Num $r.$name; if ($null -ne $x -and $x -ge 0) { $vals += $x } }
    if ($vals.Count -eq 0) { return $null }
    return [math]::Round(($vals | Measure-Object -Maximum).Maximum,2)
}
function Get-Avg($rows,$name) {
    $vals = @(); foreach ($r in $rows) { $x = Num $r.$name; if ($null -ne $x -and $x -ge 0) { $vals += $x } }
    if ($vals.Count -eq 0) { return $null }
    return [math]::Round(($vals | Measure-Object -Average).Average,2)
}
function Get-CpuPowerLimitFromRows($Rows) {
    $candidates=@()
    foreach($row in @($Rows)) {
        $power = Num $row.CPU_Package_Power_W
        $percent = Num $row.CPU_Power_Limit_Percent
        if($null -eq $power -or $null -eq $percent -or $power -le 0 -or $percent -lt 5 -or $percent -gt 100) { continue }
        $candidates += ($power * 100.0 / $percent)
    }
    if($candidates.Count -eq 0) { return $null }
    $ordered=@($candidates | Sort-Object)
    $middle=[int][math]::Floor($ordered.Count / 2)
    if(($ordered.Count % 2) -eq 0) { $result=([double]$ordered[$middle-1]+[double]$ordered[$middle])/2.0 }
    else { $result=[double]$ordered[$middle] }
    return [math]::Round($result,2)
}
function Find-Exe([string[]]$Names,[string[]]$Roots) {
    foreach ($n in $Names) { $c = Get-Command $n -ErrorAction SilentlyContinue; if ($c -and $c.Source) { return $c.Source } }
    foreach ($r in $Roots) {
        if (!(Test-Path $r)) { continue }
        foreach ($n in $Names) {
            $f = Get-ChildItem -Path $r -Filter $n -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($f) { return $f.FullName }
        }
    }
    return $null
}
$script:VCRuntimeChecked = $false
function Ensure-VCRuntime {
    if ($script:VCRuntimeChecked) { return $true }
    $script:VCRuntimeChecked = $true

    $x64Dll = Join-Path $env:WINDIR "System32\VCRUNTIME140.dll"
    $x86Dll = Join-Path $env:WINDIR "SysWOW64\VCRUNTIME140.dll"
    $x64Ready = Test-Path $x64Dll
    $x86Ready = Test-Path $x86Dll

    if ($x64Ready -and $x86Ready) {
        Log "[VCREDIST] Microsoft Visual C++ runtime is ready."
        return $true
    }

    Log "[VCREDIST] VCRUNTIME140.dll is missing. Installing Microsoft Visual C++ 2015-2022 runtime (x64 + x86)."
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (!$winget) {
        Log "[WARN] winget.exe not found. Cannot automatically install Microsoft Visual C++ runtime."
        return $false
    }

    $packageIds = @(
        "Microsoft.VCRedist.2015+.x64",
        "Microsoft.VCRedist.2015+.x86"
    )

    foreach ($packageId in $packageIds) {
        try {
            Log "[VCREDIST] Installing: $packageId"
            & $winget.Source install --id $packageId --exact --accept-package-agreements --accept-source-agreements --silent
            if ($LASTEXITCODE -ne 0) {
                Log "[WARN] VC++ runtime install returned exit code $LASTEXITCODE for $packageId."
            }
        } catch {
            Log "[WARN] VC++ runtime install failed for ${packageId}: $($_.Exception.Message)"
        }
    }

    $x64Ready = Test-Path $x64Dll
    $x86Ready = Test-Path $x86Dll
    if ($x64Ready -and $x86Ready) {
        Log "[VCREDIST] Microsoft Visual C++ runtime installation completed."
        return $true
    }

    Log "[WARN] Microsoft Visual C++ runtime is still incomplete. y-cruncher may fail to start."
    return $false
}

function Download-FileWithFallback([string]$Name,[string[]]$Urls,[string]$OutFile) {
    foreach ($u in $Urls) {
        if ([string]::IsNullOrWhiteSpace($u)) { continue }
        try {
            Log "[DOWNLOAD] $Name try: $u"
            Invoke-WebRequest -Uri $u -OutFile $OutFile -UseBasicParsing -TimeoutSec 300
            if ((Test-Path $OutFile) -and ((Get-Item $OutFile).Length -gt 0)) { Log "[DOWNLOAD] $Name OK"; return $true }
        } catch { Log "[WARN] $Name download failed: $($_.Exception.Message)" }
    }
    return $false
}
function Get-SevenZipPortable {
    $sevenDir = Join-Path $ToolRoot "7zip"
    $sevenExe = Join-Path $sevenDir "7z.exe"

    if (Test-Path $sevenExe) { return $sevenExe }

    New-Item -ItemType Directory -Force -Path $sevenDir | Out-Null

    # 使用完整 7-Zip，不使用 7zr.exe。
    # y-cruncher 压缩包包含大量特殊文件名，7zr 精简版兼容性不足。
    $installer = Join-Path $sevenDir "7z-installer.exe"
    $url = "https://www.7-zip.org/a/7z2409-x64.exe"

    try {
        Log "[7ZIP] Download full 7-Zip"
        Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing -TimeoutSec 120

        if(Test-Path $installer){
            Log "[7ZIP] Install full 7-Zip silently"
            Start-Process -FilePath $installer -ArgumentList "/S" -Wait -WindowStyle Hidden
        }

        $candidates = @(
            "$env:ProgramFiles\7-Zip\7z.exe",
            "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
        )

        foreach($c in $candidates){
            if(Test-Path $c){
                Copy-Item $c $sevenExe -Force
                Remove-Item $installer -Force -ErrorAction SilentlyContinue
                Log "[7ZIP] Ready: $sevenExe"
                return $sevenExe
            }
        }
    } catch {
        Log "[WARN] 7zip install failed: $($_.Exception.Message)"
    }

    return $null
}

function Expand-Zip($Zip,$Dest) {
    if (Test-Path $Dest) { Remove-Item $Dest -Recurse -Force -ErrorAction SilentlyContinue }
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null

    # 优先使用 7-Zip，兼容 y-cruncher 中大量特殊文件名
    $seven = Get-SevenZipPortable
    if ($seven) {
        try {
            Log "[7ZIP] Extract: $Zip"
            & $seven x $Zip "-o$Dest" -y | Out-Null
            if ($LASTEXITCODE -eq 0) { return $true }
        } catch {
            Log "[WARN] 7zip extraction failed: $($_.Exception.Message)"
        }
    }

    try { Expand-Archive -Path $Zip -DestinationPath $Dest -Force; return $true } catch {}
    try {
        $tar = Get-Command tar.exe -ErrorAction SilentlyContinue
        if ($tar) { & $tar.Source -xf $Zip -C $Dest; if ($LASTEXITCODE -eq 0) { return $true } }
    } catch {}
    return $false
}

function Get-FirstNvidiaGpuName {
    try {
        $g = & nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>$null | Select-Object -First 1
        if($g){ return ("$g").Trim() }
    } catch {}
    return ""
}

function Get-GpuHardwareLimits {
    $powerLimits = @()
    $slowdownTemps = @()
    try {
        $raw = & nvidia-smi --query-gpu=power.limit --format=csv,noheader,nounits 2>$null
        foreach($line in @($raw)) {
            $value = Num ("$line".Trim())
            if($null -ne $value -and $value -gt 0) { $powerLimits += $value }
        }
    } catch {}
    try {
        # Query output is driver-owned and may omit this field; never infer it from GPU model.
        $thermalDetail = & nvidia-smi -q -d TEMPERATURE 2>$null
        foreach($line in @($thermalDetail)) {
            if("$line" -match 'GPU Slowdown Temp\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*C') {
                $slowdownTemps += [double]$matches[1]
            }
        }
    } catch {}
    return [pscustomobject]@{
        PowerLimitW = if($powerLimits.Count -gt 0){[math]::Round(($powerLimits | Measure-Object -Sum).Sum,2)}else{$null}
        ThermalSlowdownC = if($slowdownTemps.Count -gt 0){[math]::Round(($slowdownTemps | Measure-Object -Minimum).Minimum,1)}else{$null}
    }
}

function Get-CpuOfficialTdpW([string]$CpuName) {
    if($CpuOfficialTdpW -gt 0) { return [double]$CpuOfficialTdpW }
    # Keep this catalog exact-match only; do not derive TDP from CPU family, clock, or core count.
    if($CpuName -match 'Ryzen 9 9950X') { return 170 }
    return $null
}

function Normalize-DriveLetter([string]$Drive) {
    if([string]::IsNullOrWhiteSpace($Drive)){ return "" }
    $d = $Drive.Trim().TrimEnd('\')
    if($d -match '^([A-Za-z]):$'){ return ($Matches[1].ToUpper() + ':') }
    if($d -match '^([A-Za-z])$'){ return ($Matches[1].ToUpper() + ':') }
    return $d.ToUpper()
}
function Get-DiskObjectPropertyValue([object]$Obj, [string[]]$Names) {
    if($null -eq $Obj){ return $null }
    foreach($n in $Names){
        try {
            $prop = $Obj.PSObject.Properties[$n]
            if($prop -and $null -ne $prop.Value -and "$($prop.Value)" -ne "") { return $prop.Value }
        } catch {}
    }
    return $null
}
function Get-DiskRotationRateValue([object]$Obj) {
    $v = Get-DiskObjectPropertyValue $Obj @("RotationRate","SpindleSpeed","NominalMediaRotationRate")
    if($null -eq $v){ return $null }
    try {
        $s = "$v".Trim()
        if($s -match '^[0-9]+$'){ return [int]$s }
    } catch {}
    return $null
}

function Convert-DiskSpdNumber([object]$Value) {
    if($null -eq $Value){ return $null }
    $s = ([string]$Value).Trim()
    if([string]::IsNullOrWhiteSpace($s)){ return $null }
    $s = $s.Replace([char]0x00A0,' ').Trim()
    $styles = [Globalization.NumberStyles]::Float -bor [Globalization.NumberStyles]::AllowThousands
    [double]$n = 0
    if([double]::TryParse($s,$styles,[Globalization.CultureInfo]::InvariantCulture,[ref]$n)){ return $n }
    if([double]::TryParse($s,$styles,[Globalization.CultureInfo]::CurrentCulture,[ref]$n)){ return $n }

    $s2 = ($s -replace '\s','')
    if($s2 -match '^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$'){
        $s2 = $s2 -replace ',',''
    } elseif($s2 -match '^[+-]?\d+,\d+$' -and $s2 -notmatch '\.'){
        $s2 = $s2 -replace ',','.'
    }
    [double]$n2 = 0
    if([double]::TryParse($s2,[Globalization.NumberStyles]::Float,[Globalization.CultureInfo]::InvariantCulture,[ref]$n2)){ return $n2 }
    return $null
}
function Format-DiskNumber([object]$Value,[int]$Decimals=2,[bool]$Thousands=$false) {
    $n = Convert-DiskSpdNumber $Value
    if($null -eq $n){ return "-" }
    if($Thousands){ return $n.ToString(("N{0}" -f $Decimals),[Globalization.CultureInfo]::InvariantCulture) }
    return $n.ToString(("F{0}" -f $Decimals),[Globalization.CultureInfo]::InvariantCulture)
}
function Get-DiskProfileDisplayName([string]$Profile) {
    switch -Regex ("$Profile") {
        '^NVMe SSD$' { return "NVMe 固态硬盘" }
        '^SATA SSD$' { return "SATA 固态硬盘" }
        '^SAS SSD$' { return "SAS 固态硬盘" }
        '^SSD$|^Generic SSD$' { return "固态硬盘（接口未完全识别）" }
        '^SATA HDD$' { return "SATA 机械硬盘" }
        '^SAS HDD$' { return "SAS 机械硬盘" }
        '^HDD$' { return "机械硬盘（接口未完全识别）" }
        '^RAID SSD$' { return "阵列或存储控制器下的固态磁盘" }
        '^RAID HDD$' { return "阵列或存储控制器下的机械磁盘" }
        '^Controller Logical Disk$|^RAID/Virtual Disk$|^RAID/Storage$' { return "存储控制器逻辑磁盘（物理型号未透传）" }
        '^Virtual Disk$' { return "虚拟磁盘" }
        '^USB Disk$' { return "USB 磁盘" }
        '^SATA Unknown$' { return "SATA 磁盘（介质类型未知）" }
        '^SAS Unknown$' { return "SAS 磁盘（介质类型未知）" }
        default { return "磁盘（类型未完全识别）" }
    }
}
function Get-DiskRoleDisplayName([bool]$IsSystemDrive) {
    if($IsSystemDrive){ return "系统盘" }
    return "数据盘"
}
function Get-DiskSpdSectionResult($Lines,[ValidateSet("total","read","write")][string]$SectionName) {
    $target = $SectionName.ToLower()
    $active = $false
    foreach($line0 in @($Lines)){
        $line = [string]$line0
        if($line -match '^\s*(Total|Read|Write)\s+IO\s*$'){
            $active = ($Matches[1].ToLower() -eq $target)
            continue
        }
        if($active -and $line -match '^\s*total\s*:\s*(.+)$'){
            $cols = @($Matches[1] -split '\|' | ForEach-Object { $_.Trim() })
            if($cols.Count -ge 5){
                $mb = Convert-DiskSpdNumber $cols[2]
                $io = Convert-DiskSpdNumber $cols[3]
                $lat = Convert-DiskSpdNumber $cols[4]
                if($null -ne $mb){
                    return [pscustomobject]@{MiBps=$mb;Iops=$io;AvgLatMs=$lat;Raw=$line}
                }
            }
        }
    }

    # Fallback for output variants that omit or alter the section headings.
    $totals = @()
    foreach($line0 in @($Lines)){
        $line = [string]$line0
        if($line -match '^\s*total\s*:\s*(.+)$'){
            $cols = @($Matches[1] -split '\|' | ForEach-Object { $_.Trim() })
            if($cols.Count -ge 5){
                $mb = Convert-DiskSpdNumber $cols[2]
                if($null -ne $mb){
                    $totals += [pscustomobject]@{
                        MiBps=$mb
                        Iops=(Convert-DiskSpdNumber $cols[3])
                        AvgLatMs=(Convert-DiskSpdNumber $cols[4])
                        Raw=$line
                    }
                }
            }
        }
    }
    $idx = switch($target){ "total" {0}; "read" {1}; "write" {2}; default {-1} }
    if($idx -ge 0 -and $totals.Count -gt $idx){ return $totals[$idx] }
    return $null
}
# v91 disk policy:
# - Performance "reference" values are informational targets, not vendor-model promises.
# - "Critical" values are deliberately low minimum-activity floors used only to catch a stalled,
#   unusable, or severely degraded test. They are profile-based and never tied to one SSD model.
# - System drives receive an additional relaxation because Windows, Defender, pagefile, indexing,
#   encryption, and application I/O can materially reduce mixed-random benchmark numbers.
function Get-DiskThresholdByProfile([string]$Profile,[bool]$IsSystemDrive=$false) {
    if(!$AutoHardwareThreshold){
        return [pscustomobject]@{PassMBps=$DiskThroughputPassMBps;FailMBps=$DiskThroughputFailMBps}
    }

    $base = switch -Regex ("$Profile") {
        '^NVMe SSD$' { [pscustomobject]@{PassMBps=500;FailMBps=50}; break }
        '^SATA SSD$|^SSD$|^Generic SSD$' { [pscustomobject]@{PassMBps=200;FailMBps=30}; break }
        '^SAS SSD$'  { [pscustomobject]@{PassMBps=300;FailMBps=40}; break }
        '^RAID SSD$' { [pscustomobject]@{PassMBps=200;FailMBps=25}; break }
        '^SATA HDD$' { [pscustomobject]@{PassMBps=80;FailMBps=10}; break }
        '^SAS HDD$'  { [pscustomobject]@{PassMBps=100;FailMBps=15}; break }
        '^RAID HDD$' { [pscustomobject]@{PassMBps=80;FailMBps=10}; break }
        '^HDD$'      { [pscustomobject]@{PassMBps=80;FailMBps=10}; break }
        '^Controller Logical Disk$|^RAID/Virtual Disk$|^RAID/Storage$|^Virtual Disk$' { [pscustomobject]@{PassMBps=100;FailMBps=10}; break }
        '^USB Disk$' { [pscustomobject]@{PassMBps=40;FailMBps=5}; break }
        '^SATA Unknown$' { [pscustomobject]@{PassMBps=80;FailMBps=10}; break }
        '^SAS Unknown$'  { [pscustomobject]@{PassMBps=100;FailMBps=15}; break }
        default      { [pscustomobject]@{PassMBps=100;FailMBps=10}; break }
    }

    if($IsSystemDrive){
        return [pscustomobject]@{
            PassMBps = [int][math]::Max(1,[math]::Round([double]$base.PassMBps * 0.75))
            FailMBps = [int][math]::Max(1,[math]::Round([double]$base.FailMBps * 0.75))
        }
    }
    return $base
}
function Get-DiskRandomIopsThresholdByProfile([string]$Profile,[bool]$IsSystemDrive=$false) {
    $base = switch -Regex ("$Profile") {
        '^NVMe SSD$' { [pscustomobject]@{PassIOPS=5000;FailIOPS=500}; break }
        '^SATA SSD$|^SSD$|^Generic SSD$' { [pscustomobject]@{PassIOPS=1500;FailIOPS=200}; break }
        '^SAS SSD$'  { [pscustomobject]@{PassIOPS=2500;FailIOPS=300}; break }
        '^RAID SSD$' { [pscustomobject]@{PassIOPS=1500;FailIOPS=150}; break }
        '^SATA HDD$' { [pscustomobject]@{PassIOPS=75;FailIOPS=8}; break }
        '^SAS HDD$'  { [pscustomobject]@{PassIOPS=120;FailIOPS=12}; break }
        '^RAID HDD$' { [pscustomobject]@{PassIOPS=75;FailIOPS=8}; break }
        '^HDD$'      { [pscustomobject]@{PassIOPS=75;FailIOPS=8}; break }
        '^Controller Logical Disk$|^RAID/Virtual Disk$|^RAID/Storage$|^Virtual Disk$' { [pscustomobject]@{PassIOPS=300;FailIOPS=30}; break }
        '^USB Disk$' { [pscustomobject]@{PassIOPS=100;FailIOPS=10}; break }
        '^SATA Unknown$' { [pscustomobject]@{PassIOPS=50;FailIOPS=5}; break }
        '^SAS Unknown$'  { [pscustomobject]@{PassIOPS=80;FailIOPS=8}; break }
        default      { [pscustomobject]@{PassIOPS=300;FailIOPS=30}; break }
    }

    if($IsSystemDrive){
        return [pscustomobject]@{
            PassIOPS = [int][math]::Max(1,[math]::Round([double]$base.PassIOPS * 0.70))
            FailIOPS = [int][math]::Max(1,[math]::Round([double]$base.FailIOPS * 0.50))
        }
    }
    return $base
}
function Get-DiskProfileFromFields([string]$BusType,[string]$MediaType,[string]$Model,[Nullable[int]]$RotationRate) {
    $bus = "$BusType"
    $media = "$MediaType"
    $modelText = "$Model"

    if($modelText -match '(?i)VMware|Virtual Disk|QEMU|VBOX|Virtual HD|Msft Virtual|Hyper-V'){ return "Virtual Disk" }

    # RAID/VMD/Storage Spaces is an access path, not a fault. Use media hints when available.
    if($bus -match '(?i)RAID|Storage Spaces|Spaces|VMD'){
        if(($RotationRate -ne $null -and $RotationRate -eq 0) -or $media -match '(?i)SSD|Solid State' -or $modelText -match '(?i)NVMe|SSD|Solid|PCIe|M\.2'){
            return "RAID SSD"
        }
        if(($RotationRate -ne $null -and $RotationRate -gt 0) -or $media -match '(?i)HDD|Hard Disk' -or $modelText -match '(?i)HDD|Hard|Seagate|HGST|Hitachi|TOSHIBA|Western Digital|\bWD\b|ST[0-9]|WDC'){
            return "RAID HDD"
        }
        return "Controller Logical Disk"
    }

    if($bus -match "(?i)USB") { return "USB Disk" }
    if($bus -match "(?i)NVMe" -or $modelText -match "(?i)NVMe|PCIe|M\.2") { return "NVMe SSD" }

    if($RotationRate -ne $null){
        if($RotationRate -gt 0){
            if($bus -match "(?i)SATA") { return "SATA HDD" }
            if($bus -match "(?i)SAS") { return "SAS HDD" }
            return "HDD"
        }
        if($RotationRate -eq 0){
            if($bus -match "(?i)SATA") { return "SATA SSD" }
            if($bus -match "(?i)SAS") { return "SAS SSD" }
            return "SSD"
        }
    }

    if($media -match "(?i)HDD|Hard Disk") {
        if($bus -match "(?i)SATA") { return "SATA HDD" }
        if($bus -match "(?i)SAS") { return "SAS HDD" }
        return "HDD"
    }
    if($media -match "(?i)SSD|Solid State") {
        if($bus -match "(?i)SATA") { return "SATA SSD" }
        if($bus -match "(?i)SAS") { return "SAS SSD" }
        return "SSD"
    }

    if($modelText -match "(?i)SSD|Solid") {
        if($bus -match "(?i)SATA") { return "SATA SSD" }
        if($bus -match "(?i)SAS") { return "SAS SSD" }
        return "SSD"
    }
    if($modelText -match "(?i)HDD|Hard|Seagate|HGST|Hitachi|TOSHIBA|Western Digital|\bWD\b|ST[0-9]|WDC") {
        if($bus -match "(?i)SATA") { return "SATA HDD" }
        if($bus -match "(?i)SAS") { return "SAS HDD" }
        return "HDD"
    }

    if($bus -match "(?i)SATA") { return "SATA Unknown" }
    if($bus -match "(?i)SAS") { return "SAS Unknown" }
    return "Generic Disk"
}
function Get-DiskProfileForDrive([string]$Drive) {
    $driveNorm = Normalize-DriveLetter $Drive
    $letter = $driveNorm.TrimEnd(':')
    $systemDrive = Normalize-DriveLetter $env:SystemDrive
    $isSystem = ($driveNorm -eq $systemDrive)
    $diskNumber = $null
    $bus = ""
    $media = ""
    $model = ""
    $rotationRate = $null
    $profile = "Generic Disk"
    $source = "Fallback"
    $detectionEvidence = ""
    try {
        $part = Get-Partition -DriveLetter $letter -ErrorAction SilentlyContinue | Select-Object -First 1
        if($part){
            $diskNumber = $part.DiskNumber
            $disk = Get-Disk -Number $diskNumber -ErrorAction SilentlyContinue
            if($disk){
                $bus = "$($disk.BusType)"
                $media = "$($disk.MediaType)"
                $model = "$($disk.FriendlyName)"
                $rotationRate = Get-DiskRotationRateValue $disk
                $diskSerial = "$(Get-DiskObjectPropertyValue $disk @("SerialNumber"))"

                try {
                    $wmi = Get-CimInstance Win32_DiskDrive -Filter ("Index={0}" -f $diskNumber) -ErrorAction SilentlyContinue | Select-Object -First 1
                    if($wmi){
                        $wmiModel = "$(Get-DiskObjectPropertyValue $wmi @("Model","Caption"))"
                        $wmiMedia = "$(Get-DiskObjectPropertyValue $wmi @("MediaType"))"
                        $wmiInterface = "$(Get-DiskObjectPropertyValue $wmi @("InterfaceType"))"
                        $wmiPnp = "$(Get-DiskObjectPropertyValue $wmi @("PNPDeviceID"))"
                        $wmiSerial = "$(Get-DiskObjectPropertyValue $wmi @("SerialNumber"))"
                        if([string]::IsNullOrWhiteSpace($model) -or $model -match '(?i)^Disk\s+\d+$|Microsoft Storage Space Device'){ $model = $wmiModel }
                        if([string]::IsNullOrWhiteSpace($media) -or $media -match '(?i)Unspecified|Unknown'){ $media = $wmiMedia }
                        if([string]::IsNullOrWhiteSpace($diskSerial)){ $diskSerial = $wmiSerial }
                        $detectionEvidence = "$wmiModel $wmiMedia $wmiInterface $wmiPnp"
                    }
                } catch {}

                try {
                    $allPhysical = @(Get-PhysicalDisk -ErrorAction SilentlyContinue)
                    $pdMatch = @($allPhysical | Where-Object {
                        $pdModel = "$(Get-DiskObjectPropertyValue $_ @("FriendlyName","Model"))"
                        $pdSerial = "$(Get-DiskObjectPropertyValue $_ @("SerialNumber"))"
                        $pdDeviceId = "$(Get-DiskObjectPropertyValue $_ @("DeviceId"))"
                        ($pdModel -and $model -and $pdModel -eq $model) -or
                        ($pdSerial -and $diskSerial -and $pdSerial.Trim() -eq $diskSerial.Trim()) -or
                        ($pdDeviceId -and $null -ne $diskNumber -and $pdDeviceId -eq "$diskNumber")
                    })
                    if($pdMatch.Count -eq 1){
                        $pd = $pdMatch[0]
                        $pdBus = Get-DiskObjectPropertyValue $pd @("BusType")
                        $pdMedia = Get-DiskObjectPropertyValue $pd @("MediaType")
                        $pdModel = Get-DiskObjectPropertyValue $pd @("FriendlyName","Model")
                        $pdRotation = Get-DiskRotationRateValue $pd
                        if([string]::IsNullOrWhiteSpace($bus) -or $bus -eq "Unknown") { $bus = "$pdBus" }
                        if([string]::IsNullOrWhiteSpace($media) -or $media -eq "Unspecified" -or $media -eq "Unknown") { $media = "$pdMedia" }
                        if([string]::IsNullOrWhiteSpace($model)) { $model = "$pdModel" }
                        if($rotationRate -eq $null) { $rotationRate = $pdRotation }
                    }
                } catch {}

                $profileInputModel = ("{0} {1}" -f $model,$detectionEvidence).Trim()
                $profile = Get-DiskProfileFromFields $bus $media $profileInputModel $rotationRate
                $source = "Get-Partition/Get-Disk + Win32_DiskDrive/Get-PhysicalDisk"
            }
        }
    } catch {}
    if($profile -eq "Generic Disk"){
        try {
            $physicalDisks = @(Get-PhysicalDisk -ErrorAction SilentlyContinue)
            if($physicalDisks.Count -eq 1){
                $pd = $physicalDisks[0]
                $bus = "$(Get-DiskObjectPropertyValue $pd @("BusType"))"
                $media = "$(Get-DiskObjectPropertyValue $pd @("MediaType"))"
                $model = "$(Get-DiskObjectPropertyValue $pd @("FriendlyName","Model"))"
                $rotationRate = Get-DiskRotationRateValue $pd
                $profile = Get-DiskProfileFromFields $bus $media $model $rotationRate
                $source = "Get-PhysicalDisk single-disk fallback"
            } elseif($physicalDisks.Count -gt 1) {
                $source = "Unresolved; skipped unsafe multi-disk fallback"
            }
        } catch {}
    }
    $th = Get-DiskThresholdByProfile $profile $isSystem
    return [pscustomobject]@{
        Drive = $driveNorm
        DiskNumber = $diskNumber
        Profile = $profile
        ProfileDisplay = (Get-DiskProfileDisplayName $profile)
        BusType = $bus
        MediaType = $media
        RotationRate = $rotationRate
        Model = $model
        IsSystemDrive = $isSystem
        PassMBps = $th.PassMBps
        FailMBps = $th.FailMBps
        Source = $source
    }
}
function Get-DiskProfile {
    try {
        $first = Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" -ErrorAction SilentlyContinue | Sort-Object DeviceID | Select-Object -First 1
        if($first){ return (Get-DiskProfileForDrive $first.DeviceID).Profile }
    } catch {}
    return "Generic Disk"
}
function Initialize-DiskDriveProfiles([string[]]$Drives) {
    $script:DiskDriveProfiles = @{}
    $lines = @()
    foreach($d0 in $Drives){
        $d = Normalize-DriveLetter $d0
        if([string]::IsNullOrWhiteSpace($d)){ continue }
        $info = Get-DiskProfileForDrive $d
        $script:DiskDriveProfiles[$d] = $info
        $sys = if($info.IsSystemDrive){"system"}else{"data"}
        $iops = Get-DiskRandomIopsThresholdByProfile $info.Profile $info.IsSystemDrive
        $lines += ("{0}={1}; {2}; DiskNumber={3}; Bus={4}; Media={5}; RotationRate={6}; Model={7}; ThroughputRef>={8}MB/s; ThroughputMin>={9}MB/s; RandomRef>={10}IOPS; RandomMin>={11}IOPS" -f $d,$info.Profile,$sys,$info.DiskNumber,$info.BusType,$info.MediaType,$info.RotationRate,$info.Model,$info.PassMBps,$info.FailMBps,$iops.PassIOPS,$iops.FailIOPS)
        Log ("[DISK PROFILE] {0} Profile={1} SystemDrive={2} DiskNumber={3} Bus={4} Media={5} RotationRate={6} Model={7} ThroughputRefMBps={8} ThroughputMinMBps={9} RandomRefIOPS={10} RandomMinIOPS={11} Source={12}" -f $d,$info.Profile,$info.IsSystemDrive,$info.DiskNumber,$info.BusType,$info.MediaType,$info.RotationRate,$info.Model,$info.PassMBps,$info.FailMBps,$iops.PassIOPS,$iops.FailIOPS,$info.Source)
    }
    if($lines.Count -gt 0){ $script:DiskThresholdProfile = ($lines -join " | ") }
    else { $script:DiskThresholdProfile = "No disk target" }
}
function Get-DiskDriveThresholdInfo([string]$Drive) {
    $d = Normalize-DriveLetter $Drive
    if($script:DiskDriveProfiles -and $script:DiskDriveProfiles.ContainsKey($d)){ return $script:DiskDriveProfiles[$d] }
    return (Get-DiskProfileForDrive $d)
}
function Get-DiskThresholdSummaryText {
    $lines=@()
    foreach($d0 in $script:ResolvedTestDrives){
        $info = Get-DiskDriveThresholdInfo $d0
        $role = Get-DiskRoleDisplayName $info.IsSystemDrive
        $profileDisplay = Get-DiskProfileDisplayName $info.Profile
        $iops = Get-DiskRandomIopsThresholdByProfile $info.Profile $info.IsSystemDrive
        $modelText = if([string]::IsNullOrWhiteSpace("$($info.Model)")){"型号未识别"}else{"$($info.Model)"}
        $lines += ("{0} | {1} | {2} | {3} | 4K随机读写参考 >= {4} IOPS | 顺序读写参考 >= {5} MiB/s" -f $info.Drive,$role,$profileDisplay,$modelText,$iops.PassIOPS,$info.PassMBps)
    }
    if($lines.Count -eq 0){ return "-" }
    return ($lines -join "`r`n")
}
function Get-DiskThresholdSummaryHtml {
    $rows=""
    foreach($d0 in $script:ResolvedTestDrives){
        $info = Get-DiskDriveThresholdInfo $d0
        $role = Get-DiskRoleDisplayName $info.IsSystemDrive
        $profileDisplay = Get-DiskProfileDisplayName $info.Profile
        $iops = Get-DiskRandomIopsThresholdByProfile $info.Profile $info.IsSystemDrive
        $modelText = if([string]::IsNullOrWhiteSpace("$($info.Model)")){"型号未识别"}else{"$($info.Model)"}
        $rows += ("<tr><td><b>{0}</b><br><span class='muted'>{1}</span></td><td><b>{2}</b><br><span class='muted'>{3}</span></td><td>≥ {4} IOPS</td><td>≥ {5} MiB/s</td></tr>" -f `
            (Html $info.Drive),(Html $role),(Html $profileDisplay),(Html $modelText),`
            (Format-DiskNumber $iops.PassIOPS 0 $true),(Format-DiskNumber $info.PassMBps 0 $true))
    }
    if([string]::IsNullOrWhiteSpace($rows)){
        return "<div class='muted'>未启用磁盘测试。</div>"
    }
    return @"
<table class='disk-reference-table'>
<tr><th style='width:14%'>盘符</th><th>磁盘类型与型号</th><th style='width:23%'>4K 随机读写参考</th><th style='width:23%'>顺序读写参考</th></tr>
$rows
</table>
<div class='small'>参考值用于性能对比。实测值低于参考值时标记“关注”，不会直接判定硬盘故障；仅在出现 I/O 错误、测试中断、无有效结果或性能严重异常时判定不合格。</div>
"@
}

function Apply-AutoHardwareThresholds {
    if(!$AutoHardwareThreshold){ return }
    try {
        $cpus = @(Get-CimInstance Win32_Processor -ErrorAction SilentlyContinue)
        $cpuName = ""
        if($cpus.Count -gt 0){ $cpuName = "$($cpus[0].Name) $($cpus[0].Manufacturer)" }
        $script:CpuOfficialTdpW = Get-CpuOfficialTdpW $cpuName
        if($null -ne $script:CpuOfficialTdpW) {
            $script:CpuOfficialTdpSource = if($CpuOfficialTdpW -gt 0){"parameter override"}else{"local exact CPU TDP catalog"}
        }
        $script:CpuThresholdProfile = "Generic CPU"
        if($cpuName -match "EPYC|Xeon"){
            # Server CPU: allow higher sustained temperature under HPC full load.
            # Warning: elevated temperature. Fail: thermal throttling risk / abnormal cooling.
            $script:CpuThresholdProfile = "Server CPU / IPMI-first"
            $script:CpuTempWarnC = 90
            $script:CpuTempFailC = 95
        } elseif($cpuName -match "Core\(TM\)|Core |Ryzen|Threadripper"){
            $script:CpuThresholdProfile = "Workstation/Desktop CPU"
            $script:CpuTempWarnC = 90
            $script:CpuTempFailC = 100
        } else {
            $script:CpuThresholdProfile = "Generic CPU"
            $script:CpuTempWarnC = 85
            $script:CpuTempFailC = 95
        }
    } catch { $script:CpuThresholdProfile = "Generic CPU" }

    try {
        $gpuName = Get-FirstNvidiaGpuName
        $script:GpuThresholdProfile = "Generic NVIDIA GPU"
        if($gpuName -match "RTX 5090|RTX 4090") { $script:GpuPowerPassW = 300; $script:GpuTempWarnC = 85; $script:GpuTempFailC = 95; $script:GpuThresholdProfile = "High-power GeForce / 4090-5090 class" }
        elseif($gpuName -match "RTX 3090|RTX 3090 Ti") { $script:GpuPowerPassW = 250; $script:GpuTempWarnC = 85; $script:GpuTempFailC = 95; $script:GpuThresholdProfile = "High-power GeForce / 3090 class" }
        elseif($gpuName -match "RTX 5080|RTX 4080") { $script:GpuPowerPassW = 220; $script:GpuTempWarnC = 85; $script:GpuTempFailC = 95; $script:GpuThresholdProfile = "Upper GeForce / 4080-5080 class" }
        elseif($gpuName -match "RTX 5070|RTX 4070") { $script:GpuPowerPassW = 150; $script:GpuTempWarnC = 85; $script:GpuTempFailC = 95; $script:GpuThresholdProfile = "Mid GeForce / 4070-5070 class" }
        elseif($gpuName -match "RTX 5060|RTX 4060") { $script:GpuPowerPassW = 90; $script:GpuTempWarnC = 85; $script:GpuTempFailC = 95; $script:GpuThresholdProfile = "Entry/Mid GeForce / 4060-5060 class" }
        elseif($gpuName -match "RTX 3080|RTX 2080 Ti") { $script:GpuPowerPassW = 200; $script:GpuTempWarnC = 85; $script:GpuTempFailC = 95; $script:GpuThresholdProfile = "Older high-power GeForce" }
        elseif($gpuName -match "RTX 3070|RTX 3060") { $script:GpuPowerPassW = 100; $script:GpuTempWarnC = 85; $script:GpuTempFailC = 95; $script:GpuThresholdProfile = "Older mid GeForce" }
        elseif($gpuName -match "A100") { $script:GpuPowerPassW = 150; $script:GpuTempWarnC = 85; $script:GpuTempFailC = 95; $script:GpuThresholdProfile = "NVIDIA data-center GPU / A100 class" }
        elseif($gpuName -match "H100|H200|B200") { $script:GpuPowerPassW = 300; $script:GpuTempWarnC = 85; $script:GpuTempFailC = 95; $script:GpuThresholdProfile = "NVIDIA data-center GPU / H-B class" }
        elseif($gpuName -match "L40|L40S|L4") { $script:GpuPowerPassW = 120; $script:GpuTempWarnC = 85; $script:GpuTempFailC = 95; $script:GpuThresholdProfile = "NVIDIA data-center inference GPU" }
        else { $script:GpuPowerPassW = 80; $script:GpuTempWarnC = 85; $script:GpuTempFailC = 95; $script:GpuThresholdProfile = "Generic NVIDIA GPU" }
        $script:DetectedGpuNameForThreshold = $gpuName
        $gpuLimits = Get-GpuHardwareLimits
        $script:GpuPowerLimitW = $gpuLimits.PowerLimitW
        $script:GpuThermalSlowdownC = $gpuLimits.ThermalSlowdownC
        if($null -ne $script:GpuPowerLimitW) {
            $script:GpuPowerPassW = [math]::Round([double]$script:GpuPowerLimitW * 0.70,2)
            $script:GpuHardwareLimitSource = "nvidia-smi power.limit"
        }
        if($null -ne $script:GpuThermalSlowdownC) {
            $script:GpuTempWarnC = [math]::Round([double]$script:GpuThermalSlowdownC - 10,1)
            $script:GpuTempFailC = $script:GpuThermalSlowdownC
            if($script:GpuHardwareLimitSource -eq "Unavailable") { $script:GpuHardwareLimitSource = "nvidia-smi GPU Slowdown Temp" }
            else { $script:GpuHardwareLimitSource += " + GPU Slowdown Temp" }
        }
    } catch { $script:GpuThresholdProfile = "Generic NVIDIA GPU" }

    try {
        $script:DiskThresholdProfile = "Per-drive dynamic disk threshold; initialized after drive resolution"
    } catch { $script:DiskThresholdProfile = "Per-drive dynamic disk threshold" }

    Log ("[THRESHOLD] AutoHardwareThreshold={0}; CPU={1}; GPU={2}; Disk={3}; GpuPowerPassW={4}; GpuPowerLimitW={5}; GpuThermalSlowdownC={6}; GpuLimitSource={7}; DiskGlobalFallbackPassMBps={8}; DiskGlobalFallbackFailMBps={9}" -f $AutoHardwareThreshold,$script:CpuThresholdProfile,$script:GpuThresholdProfile,$script:DiskThresholdProfile,$GpuPowerPassW,$script:GpuPowerLimitW,$script:GpuThermalSlowdownC,$script:GpuHardwareLimitSource,$DiskThroughputPassMBps,$DiskThroughputFailMBps)
}

Apply-AutoHardwareThresholds


function Initialize-StressToolPreparation {
    Stage-Message "[准备] 正在准备压测工具..."
    Log "[PREPARE] 开始准备压测工具环境"
    Log "========================================"
    Log "[PRECHECK] 开始测试工具准备检查"
    Log "========================================"

    $failed = $false

    $checks = @(
        @{Name="FurMark2"; Action={
            $roots=@($ToolRoot,$LocalFurMark2Dir,$ReportBase)
            $e=Find-Exe @("furmark.exe","FurMark.exe","FurMark2.exe","furmark2.exe") $roots
            if(!$e -and $AutoDownloadFurMark2){
                $e=Install-ZipTool "FurMark2" $LocalFurMark2Dir @("furmark.exe","FurMark.exe","FurMark2.exe","furmark2.exe") (@($FurMark2Url)+$FurMark2FallbackUrls)
            }
            return $e
        }},
        @{Name="y-cruncher"; Action={
            $roots=@($ToolRoot,$LocalYCruncherDir,$ReportBase)
            $e=Find-Exe @("y-cruncher.exe") $roots
            if(!$e -and $AutoDownloadYCruncher){
                $e=Install-ZipTool "y-cruncher" $LocalYCruncherDir @("y-cruncher.exe") (@($YCruncherUrl)+$YCruncherFallbackUrls)
            }
            if($e){ [void](Ensure-VCRuntime) }
            return $e
        }},
        @{Name="DiskSpd"; Action={
            $roots=@($ToolRoot,$LocalDiskSpdDir,$ReportBase)
            $e=Find-Exe @("diskspd.exe") $roots
            if(!$e -and $AutoDownloadDiskSpd){
                $e=Install-ZipTool "DiskSpd" $LocalDiskSpdDir @("diskspd.exe") (@($DiskSpdUrl)+$DiskSpdFallbackUrls)
            }
            return $e
        }}
    )

    foreach($c in $checks){
        Log "[CHECK] $($c.Name)"
        try {
            $exe=& $c.Action
            if($exe){
                Log "[OK] $($c.Name) ready: $exe"
            } else {
                Log "[ERROR] $($c.Name) preparation failed"
                $failed=$true
            }
        } catch {
            Log "[ERROR] $($c.Name) exception: $($_.Exception.Message)"
            $failed=$true
        }
    }

    if($EnableCpuTemperature -or $EnableCpuPower){
        Log "[CHECK] LibreHardwareMonitor CPU telemetry"
        try {
            $dll=Find-LibreHardwareMonitorDll
            if($dll){
                Log "[OK] LibreHardwareMonitor ready: $dll"
            }else{
                Log "[WARN] LibreHardwareMonitor unavailable, temperature collection may be skipped"
            }
        }catch{
            Log "[WARN] LibreHardwareMonitor check failed: $($_.Exception.Message)"
        }
    }

    if($failed){
        Log "========================================"
        Log "[FATAL] 测试工具准备失败，停止压测"
        Log "请检查网络、下载源或手动准备 stress_tools"
        Log "========================================"
        exit 10
    }

    Log "========================================"
    Log "[PRECHECK] 所有测试工具准备完成"
    Stage-Message "[完成] 所有压测工具准备完成"
    Stage-Message "[检查] 正在检测硬件环境..."
    Log "开始进入硬件压力测试阶段"
    Log "========================================"
}


function Install-ZipTool($Name,$InstallDir,$ExeFilters,$Urls) {
    $existing = Get-ChildItem -Path $InstallDir -Include $ExeFilters -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($existing) { Log "[$Name] found: $($existing.FullName)"; return $existing.FullName }
    $zip = Join-Path $InstallDir ($Name + ".zip")
    $extract = Join-Path $InstallDir ("extracted_" + (Get-Date -Format "yyyyMMdd_HHmmss"))
    if (!(Download-FileWithFallback $Name $Urls $zip)) { return $null }
    if (!(Expand-Zip $zip $extract)) { Log "[WARN] $Name extraction failed"; return $null }
    $exe = Get-ChildItem -Path $extract -Include $ExeFilters -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($exe) { Log "[$Name] installed: $($exe.FullName)"; return $exe.FullName }
    return $null
}
function Resolve-TestDrives {
    $targets = @()
    if ($TestAllFixedDrives) {
        # v55: test every local fixed drive, including C:, then apply per-drive physical-disk profiles and thresholds.
        $targets = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" -ErrorAction SilentlyContinue | Where-Object {$_.DeviceID -match '^[A-Z]:'} | Sort-Object DeviceID | ForEach-Object {$_.DeviceID})
        return @($targets | Select-Object -Unique)
    }
    if ($TestDrives.Count -gt 0) { foreach ($d in $TestDrives) { if ($d -match '^[A-Za-z]:$') { $targets += $d.ToUpper() } } }
    if ($targets.Count -eq 0 -and $TestDrive -match '^[A-Za-z]:$') { $targets += $TestDrive.ToUpper() }
    return @($targets | Select-Object -Unique)
}
function Assert-TestDrives([string[]]$Drives) {
    if (!$Drives -or $Drives.Count -eq 0) {
        Log "[WARN] No local fixed disk found. Disk phase will be skipped."
        $script:SkipDiskPhase = $true
        $script:DiskModuleReason = "未检测到可测试的本地固定磁盘"
        return
    }
    $need = Convert-SizeToBytes $DiskFileSize
    foreach ($d in $Drives) {
        $ps = Get-PSDrive -Name $d.TrimEnd(':') -ErrorAction SilentlyContinue
        if (!$ps) { Log "[WARN] Disk target not found: $d"; continue }
        Log ("[CHECK] {0} free={1}GB required={2}GB" -f $d,(ToGB $ps.Free),(ToGB $need))
        if ($ps.Free -lt ($need + 5GB)) { Log "[ERROR] $d free space is not enough for DiskFileSize=$DiskFileSize"; exit 2 }
    }
}
function Has-NvidiaGpu {
    try { $r = & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null; return ($LASTEXITCODE -eq 0 -and $r) } catch { return $false }
}
function Get-CurrentCpuLoadPercent {
    try { return [math]::Round((Get-Counter '\Processor(_Total)\% Processor Time').CounterSamples.CookedValue,2) } catch { return -1 }
}
function Find-LibreHardwareMonitorDll {
    $dll = Get-ChildItem -Path $LocalLibreHardwareMonitorDir -Filter "LibreHardwareMonitorLib.dll" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($dll) { return $dll.FullName }
    if ($AutoDownloadLibreHardwareMonitor) {
        return (Install-ZipTool "LibreHardwareMonitor" $LocalLibreHardwareMonitorDir @("LibreHardwareMonitorLib.dll") (@($LibreHardwareMonitorUrl)+$LibreHardwareMonitorFallbackUrls))
    }
    return $null
}
function Start-LibreHardwareMonitorGuiIfNeeded([string]$DllPath) {
    if (!$StartLibreHardwareMonitorGui) { return }
    try {
        $root = Split-Path -Parent $DllPath
        $exe = Get-ChildItem -Path $root -Filter "LibreHardwareMonitor.exe" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
        if (!$exe) { $exe = Get-ChildItem -Path $LocalLibreHardwareMonitorDir -Filter "LibreHardwareMonitor.exe" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1 }
        if ($exe) {
            $running = Get-Process -Name "LibreHardwareMonitor" -ErrorAction SilentlyContinue
            if (!$running) {
                Log "[LHM] Starting LibreHardwareMonitor GUI for sensor initialization: $($exe.FullName)"
                Start-Process -FilePath $exe.FullName -WindowStyle Minimized | Out-Null
                if ($CpuTempPreInitSeconds -gt 0) { Start-Sleep -Seconds $CpuTempPreInitSeconds }
            }
        }
    } catch { Log "[LHM] GUI start skipped: $($_.Exception.Message)" }
}
function Test-IsAdministrator {
    try {
        $id = [Security.Principal.WindowsIdentity]::GetCurrent()
        $p = New-Object Security.Principal.WindowsPrincipal($id)
        return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch { return $false }
}
function Test-LhmPawnIoInstalled {
    try {
        $t = [type]::GetType("LibreHardwareMonitor.PawnIo.PawnIo, LibreHardwareMonitorLib", $false)
        if ($null -eq $t) {
            $t = [AppDomain]::CurrentDomain.GetAssemblies() |
                ForEach-Object { $_.GetType("LibreHardwareMonitor.PawnIo.PawnIo", $false) } |
                Where-Object { $_ -ne $null } |
                Select-Object -First 1
        }
        if ($null -eq $t) { return $null }

        $prop = $t.GetProperty("IsInstalled", [Reflection.BindingFlags]"Public,Static")
        if ($null -eq $prop) { return $null }
        return [bool]$prop.GetValue($null, $null)
    } catch { return $null }
}
function Wait-PawnIoInstallation {
    $deadline = (Get-Date).AddSeconds([Math]::Max(1, $PawIoConfirmTimeoutSeconds))
    do {
        if ((Test-LhmPawnIoInstalled) -eq $true) { return $true }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    return $false
}
function Install-PawnIoSilently {
    if (!$AutoConfirmPawIoInstall) {
        Log "[LHM] PawnIO automatic installation is disabled by parameter."
        return $false
    }
    if (!(Test-IsAdministrator)) {
        Log "[LHM][WARN] PawnIO automatic installation requires an elevated PowerShell session."
        return $false
    }

    $installer = Join-Path $LocalPawnIoDir "PawnIO_setup.exe"
    $downloadUrl = "https://github.com/namazso/PawnIO.Setup/releases/latest/download/PawnIO_setup.exe"
    Remove-Item -Path $installer -Force -ErrorAction SilentlyContinue
    if (!(Download-FileWithFallback "PawnIO installer" @($downloadUrl) $installer)) {
        Log "[LHM][WARN] PawnIO installer download failed."
        return $false
    }

    try {
        $signature = Get-AuthenticodeSignature -FilePath $installer
        if ($signature.Status -ne "Valid") {
            Log "[LHM][WARN] PawnIO installer signature is invalid: $($signature.Status)"
            Remove-Item -Path $installer -Force -ErrorAction SilentlyContinue
            return $false
        }
    } catch {
        Log "[LHM][WARN] PawnIO installer signature validation failed: $($_.Exception.Message)"
        Remove-Item -Path $installer -Force -ErrorAction SilentlyContinue
        return $false
    }

    try {
        Log "[LHM] Installing signed PawnIO driver silently."
        $process = Start-Process -FilePath $installer -ArgumentList "-install -silent" -Wait -PassThru -WindowStyle Hidden
        $exitCode = $process.ExitCode
        if ($exitCode -ne 0 -and $exitCode -ne 3010) {
            Log "[LHM][WARN] PawnIO installer returned exit code $exitCode."
            return $false
        }
        if ($exitCode -eq 3010) { Log "[LHM][WARN] PawnIO installer requires a Windows restart before telemetry is available." }
        if (Wait-PawnIoInstallation) {
            Log "[LHM] PawnIO installation verified."
            return $true
        }
        Log "[LHM][WARN] PawnIO installation did not become available within $PawIoConfirmTimeoutSeconds seconds."
    } catch {
        Log "[LHM][WARN] PawnIO installer execution failed: $($_.Exception.Message)"
    }
    return $false
}
function Initialize-CpuTemperatureCollector {
    # Keep the historical function name to avoid changing the workflow.
    # From v97 onward it initializes both CPU temperature and CPU package-power telemetry.
    if (!$EnableCpuTemperature -and !$EnableCpuPower) { return }
    if ($script:LhmReady) { return }
    try {
        $dll = Find-LibreHardwareMonitorDll
        if ($dll) {
            $script:LhmDllPath = $dll
            if (!(Test-IsAdministrator)) {
                Log "[LHM][WARN] PowerShell is not running as Administrator. CPU temperature/package-power sensors may be unavailable."
            } else {
                Log "[LHM] Administrator privileges: yes"
            }

            Add-Type -Path $dll -ErrorAction Stop
            try {
                $lhmVersion = [Reflection.AssemblyName]::GetAssemblyName($dll).Version
                Log "[LHM] Assembly version: $lhmVersion"
                if ($lhmVersion -lt [version]"0.9.5.0") {
                    Log "[LHM][WARN] LibreHardwareMonitor is older than 0.9.5. Ryzen 9000/Zen 5 telemetry support may be incomplete; update the tool package."
                }
            } catch {
                Log "[LHM][WARN] Unable to read LibreHardwareMonitor assembly version."
            }

            $pawnIoInstalled = Test-LhmPawnIoInstalled
            if ($pawnIoInstalled -eq $true) {
                Log "[LHM] PawnIO installed: yes"
            } elseif ($pawnIoInstalled -eq $false) {
                Log "[LHM][WARN] PawnIO is not installed. Ryzen CPU temperature and package-power sensors can be missing."
                [void](Install-PawnIoSilently)
            } else {
                Log "[LHM] PawnIO installation state: unknown (library property unavailable)"
                Start-LibreHardwareMonitorGuiIfNeeded $dll
            }

            $c = New-Object LibreHardwareMonitor.Hardware.Computer
            $c.IsCpuEnabled = $true
            $c.IsMotherboardEnabled = $true
            $c.IsControllerEnabled = $true
            $c.IsMemoryEnabled = $true
            if ($c.PSObject.Properties.Name -contains "IsPowerMonitorEnabled") {
                $c.IsPowerMonitorEnabled = $true
            }

            $c.Open()
            $script:LhmComputer = $c
            $script:LhmReady = $true
            Log "[LHM] LibreHardwareMonitorLib loaded: $dll"

            # AMD package power is derived from an energy delta; prime it with >1 update.
            for ($i = 0; $i -lt 3; $i++) {
                foreach($hw in $c.Hardware) {
                    try { $hw.Update() } catch {}
                    foreach($sh in $hw.SubHardware) { try { $sh.Update() } catch {} }
                }
                if ($i -lt 2) { Start-Sleep -Milliseconds 650 }
            }

            Write-LhmCpuTelemetryDiagnostics
        } else {
            Log "[LHM] LibreHardwareMonitorLib.dll not found. CPU temperature will use Windows ThermalZone only; CPU package power will be unavailable."
        }
    } catch {
        $script:LhmReady = $false
        Log "[LHM] init failed: $($_.Exception.Message)"
    }
}
function Get-LhmTelemetrySensors {
    $items = @()
    if (!$script:LhmReady -or !$script:LhmComputer) { return @() }
    try {
        foreach($hw in $script:LhmComputer.Hardware) {
            try { $hw.Update() } catch {}

            $sources = @()
            $sources += [pscustomobject]@{
                Hardware = $hw
                ParentName = "$($hw.Name)"
                ParentType = "$($hw.HardwareType)"
                ParentId = "$($hw.Identifier)"
            }

            foreach($sh in $hw.SubHardware) {
                try { $sh.Update() } catch {}
                $sources += [pscustomobject]@{
                    Hardware = $sh
                    ParentName = "$($hw.Name) / $($sh.Name)"
                    ParentType = "$($sh.HardwareType)"
                    ParentId = "$($sh.Identifier)"
                }
            }

            foreach($src in $sources) {
                foreach($s in $src.Hardware.Sensors) {
                    if ($s.Value -eq $null) { continue }
                    $sensorType = "$($s.SensorType)"
                    if ($sensorType -ne "Temperature" -and $sensorType -ne "Power" -and $sensorType -ne "Load") { continue }

                    $v = [double]$s.Value
                    if ($sensorType -eq "Temperature") {
                        if ($v -le 0 -or $v -ge 130) { continue }
                    } elseif ($sensorType -eq "Power") {
                        if ($v -le 0 -or $v -ge 2000) { continue }
                    } else {
                        if ($v -lt 0 -or $v -gt 100) { continue }
                    }

                    $items += [pscustomobject]@{
                        Name = "$($s.Name)"
                        Hardware = $src.ParentName
                        HardwareType = $src.ParentType
                        HardwareId = $src.ParentId
                        SensorType = $sensorType
                        Value = [math]::Round($v,2)
                    }
                }
            }
        }
    } catch { Log "[LHM] sample failed: $($_.Exception.Message)" }
    return @($items)
}
function Select-CpuTemperatureFromSensors($Sensors) {
    if (!$Sensors -or $Sensors.Count -eq 0) { return $null }

    $temps = @($Sensors | Where-Object { $_.SensorType -eq "Temperature" })
    if ($temps.Count -eq 0) { return $null }

    $pick = @()
    if ($PreferIpmiCpuTemp) {
        $pick = @($temps | Where-Object { $_.Name -match '^(CPU_TEMP_0?[12]|CPU[ _-]?TEMP[ _-]?0?[12]|CPU_AREA_TEMP)$' })
        if ($pick.Count -eq 0) {
            $pick = @($temps | Where-Object { $_.Name -match 'CPU_TEMP|CPU AREA|CPU_AREA' })
        }
    }

    if ($pick.Count -eq 0) {
        $pick = @($temps | Where-Object {
            ($_.HardwareType -match '^Cpu$' -or $_.Hardware -match 'Ryzen|AMD|Intel|EPYC|Xeon|Processor|CPU') -and
            $_.Name -match 'CPU Package|Package|Core \(Tctl/Tdie\)|Core \(Tctl\)|Core \(Tdie\)|Tctl|Tdie|CCDs Max'
        })
    }

    if ($pick.Count -eq 0) {
        $pick = @($temps | Where-Object {
            $_.Name -match 'CPU Package|Package|Core \(Tctl/Tdie\)|Core \(Tctl\)|Core \(Tdie\)|Tctl|Tdie'
        })
    }

    if ($pick.Count -eq 0 -and $UseCpuLikeTemperatureFallback) {
        $pick = @($temps | Where-Object {
            ($_.Name -match 'CPU|Core|CCD') -or
            ($_.Hardware -match 'CPU|AMD|Intel|Ryzen|EPYC|Xeon|Processor')
        })
    }

    if ($pick.Count -eq 0) { return $null }

    $max = ($pick | Measure-Object -Property Value -Maximum).Maximum
    $names = ($pick | Sort-Object Value -Descending | Select-Object -First 3 | ForEach-Object { "$($_.Hardware):$($_.Name)" }) -join ';'
    $script:CpuTempSensorName = "LHM:$names"
    return [math]::Round([double]$max,1)
}
function Select-CpuPowerFromSensors($Sensors) {
    if (!$EnableCpuPower) { return $null }
    if (!$Sensors -or $Sensors.Count -eq 0) { return $null }

    $power = @($Sensors | Where-Object { $_.SensorType -eq "Power" })
    if ($power.Count -eq 0) { return $null }

    $cpuPower = @($power | Where-Object {
        ($_.HardwareType -match '^Cpu$' -or $_.Hardware -match 'Ryzen|AMD|Intel|EPYC|Xeon|Processor|CPU')
    })
    if ($cpuPower.Count -eq 0) {
        $cpuPower = @($power | Where-Object { $_.Name -match 'CPU|Package|PPT|Processor' })
    }
    if ($cpuPower.Count -eq 0) { return $null }

    $chosen = @()
    foreach($grp in ($cpuPower | Group-Object HardwareId)) {
        $g = @($grp.Group)
        $one = @($g | Where-Object { $_.Name -match '^Package$' } | Select-Object -First 1)
        if ($one.Count -eq 0) { $one = @($g | Where-Object { $_.Name -match '^CPU Package$|Package Power' } | Select-Object -First 1) }
        if ($one.Count -eq 0) { $one = @($g | Where-Object { $_.Name -match '^CPU PPT$|^PPT$' } | Select-Object -First 1) }
        if ($one.Count -eq 0) { $one = @($g | Where-Object { $_.Name -match 'Package|CPU|PPT|Processor' } | Sort-Object Value -Descending | Select-Object -First 1) }
        if ($one.Count -gt 0) { $chosen += $one[0] }
    }

    if ($chosen.Count -eq 0) { return $null }

    $total = ($chosen | Measure-Object -Property Value -Sum).Sum
    $names = ($chosen | ForEach-Object { "$($_.Hardware):$($_.Name)" }) -join ';'
    $script:CpuPowerSensorName = "LHM:$names"
    return [math]::Round([double]$total,2)
}
function Select-CpuPowerLimitPercentFromSensors($Sensors) {
    if (!$EnableCpuPower -or !$Sensors -or $Sensors.Count -eq 0) { return $null }
    $limits = @($Sensors | Where-Object {
        $_.SensorType -eq "Load" -and
        ($_.HardwareType -match '^Cpu$' -or $_.Hardware -match 'Ryzen|AMD|Intel|EPYC|Xeon|Processor|CPU') -and
        $_.Name -match 'PPT Limit|Package Power Limit|Power Limit'
    })
    if($limits.Count -ne 1) { return $null }
    $value = [double]$limits[0].Value
    if($value -lt 5 -or $value -gt 100) { return $null }
    $script:CpuPowerLimitSensorName = "LHM:$($limits[0].Hardware):$($limits[0].Name)"
    return [math]::Round($value,2)
}
function Write-LhmCpuTelemetryDiagnostics {
    if ($script:LhmDiagDone -or !$script:LhmReady) { return }
    $script:LhmDiagDone = $true
    try {
        $sensors = @(Get-LhmTelemetrySensors)
        $temps = @($sensors | Where-Object {
            $_.SensorType -eq "Temperature" -and
            (($_.HardwareType -match '^Cpu$') -or $_.Hardware -match 'Ryzen|AMD|Intel|EPYC|Xeon|Processor|CPU' -or $_.Name -match 'CPU|Package|Tctl|Tdie|CCD')
        })
        $powers = @($sensors | Where-Object {
            $_.SensorType -eq "Power" -and
            (($_.HardwareType -match '^Cpu$') -or $_.Hardware -match 'Ryzen|AMD|Intel|EPYC|Xeon|Processor|CPU' -or $_.Name -match 'CPU|Package|PPT|Processor')
        })

        if ($temps.Count -gt 0) {
            $desc = ($temps | Select-Object -First 12 | ForEach-Object { "$($_.Hardware) / $($_.Name)=$($_.Value)C" }) -join ' | '
            Log "[LHM] CPU temperature candidates: $desc"
        } else {
            Log "[LHM][WARN] No CPU temperature sensor returned by LibreHardwareMonitor."
        }

        if ($powers.Count -gt 0) {
            $desc = ($powers | Select-Object -First 12 | ForEach-Object { "$($_.Hardware) / $($_.Name)=$($_.Value)W" }) -join ' | '
            Log "[LHM] CPU power candidates: $desc"
        } else {
            Log "[LHM][WARN] No CPU power sensor returned by LibreHardwareMonitor."
        }
    } catch {
        Log "[LHM][WARN] CPU telemetry diagnostics failed: $($_.Exception.Message)"
    }
}
function Get-CpuTelemetrySample {
    $script:CpuTempSensorName = ""
    $script:CpuPowerSensorName = ""
    $script:CpuPowerLimitSensorName = ""

    $temp = $null
    $power = $null
    $powerLimitPercent = $null

    if (($EnableCpuTemperature -or $EnableCpuPower) -and !$script:LhmReady) {
        Initialize-CpuTemperatureCollector
    }

    $sensors = @()
    if ($script:LhmReady) {
        $sensors = @(Get-LhmTelemetrySensors)
    }

    if ($EnableCpuTemperature) {
        $temp = Select-CpuTemperatureFromSensors $sensors
        if ($null -eq $temp) {
            try {
                $tz = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue
                $vals = @()
                foreach ($t in $tz) {
                    $c = [math]::Round(($t.CurrentTemperature / 10) - 273.15, 1)
                    if ($c -gt 0 -and $c -lt 130) { $vals += $c }
                }
                if ($vals.Count -gt 0) {
                    $script:CpuTempSensorName = "Windows ThermalZone"
                    $temp = ($vals | Measure-Object -Maximum).Maximum
                }
            } catch {}
        }
        if ($null -ne $temp) { $script:CpuTempLast = $temp }
    }

    if ($EnableCpuPower) {
        $power = Select-CpuPowerFromSensors $sensors
        $powerLimitPercent = Select-CpuPowerLimitPercentFromSensors $sensors
        if ($null -ne $power) { $script:CpuPowerLast = $power }
        if ($null -ne $powerLimitPercent) { $script:CpuPowerLimitLast = $powerLimitPercent }
    }

    return [pscustomobject]@{
        TempC = $temp
        TempSensor = $script:CpuTempSensorName
        PowerW = $power
        PowerSensor = $script:CpuPowerSensorName
        PowerLimitPercent = $powerLimitPercent
        PowerLimitSensor = $script:CpuPowerLimitSensorName
    }
}
function Write-MonitorHeader {
    "Timestamp,Phase,CPU_Percent,CPU_Clock_Current_MHz,CPU_MaxClock_MHz,Memory_Used_Percent,Memory_Used_GB,Memory_Total_GB,CPU_Temperature_C,CPU_Temp_Sensor,CPU_Package_Power_W,CPU_Power_Sensor,CPU_Power_Limit_Percent,CPU_Power_Limit_Sensor,GPU_Count,GPU_Util_Max_Percent,GPU_Temp_Max_C,GPU_Fan_Max_Percent,GPU_Power_Total_W,GPU_Mem_Used_Total_MB,GPU_Mem_Total_MB,Disk_Read_MBps,Disk_Write_MBps" | Out-File $MonitorCsv -Encoding UTF8
    "Timestamp,Name,TempC,FanPercent,PowerW,PowerLimitW,UtilPercent,MemUsedMB,MemTotalMB" | Out-File $GpuSmiCsv -Encoding UTF8
    "Timestamp,Sensor,TempC" | Out-File $CpuSensorCsv -Encoding UTF8
}
function Write-GpuSmiSample {
    try {
        $raw = & nvidia-smi --query-gpu=timestamp,name,temperature.gpu,fan.speed,power.draw,power.limit,utilization.gpu,memory.used,memory.total --format=csv,noheader,nounits 2>$null
        if (!$raw) { return }
        foreach ($line in $raw) { Add-Content -Path $GpuSmiCsv -Value $line -Encoding UTF8 }
    } catch {}
}
function Write-MonitorSample([string]$Phase) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $cpu = Get-CurrentCpuLoadPercent
    $clock = $null; $maxClock = $null
    try { $p = Get-CimInstance Win32_Processor | Select-Object -First 1; $clock = $p.CurrentClockSpeed; $maxClock = $p.MaxClockSpeed } catch {}
    $memUsedPct = $null; $memUsedGB = $null; $memTotalGB = $null
    try { $os = Get-CimInstance Win32_OperatingSystem; $totalKB=[double]$os.TotalVisibleMemorySize; $freeKB=[double]$os.FreePhysicalMemory; $usedKB=$totalKB-$freeKB; $memUsedPct=[math]::Round($usedKB*100/$totalKB,2); $memUsedGB=[math]::Round($usedKB/1MB,2); $memTotalGB=[math]::Round($totalKB/1MB,2) } catch {}

    $cpuTelemetry = Get-CpuTelemetrySample
    $temp = $cpuTelemetry.TempC
    $cpuPower = $cpuTelemetry.PowerW
    $cpuPowerLimitPercent = $cpuTelemetry.PowerLimitPercent
    if ($null -ne $temp) {
        Add-Content -Path $CpuSensorCsv -Value ("$ts,$($cpuTelemetry.TempSensor),$temp") -Encoding UTF8
    }

    $gpuCount=0; $gpuUtil=$null; $gpuTemp=$null; $gpuFan=$null; $gpuPower=$null; $gpuMemUsed=0; $gpuMemTotal=0
    try {
        $g = & nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,fan.speed,power.draw,memory.used,memory.total --format=csv,noheader,nounits 2>$null
        if ($g) {
            foreach ($line in $g) {
                $gpuCount++
                $a = $line -split ',' | ForEach-Object { $_.Trim() }
                $u=Num $a[0]; $t=Num $a[1]; $fan=Num $a[2]; $pw=Num $a[3]; $mu=Num $a[4]; $mt=Num $a[5]
                if ($null -ne $u -and ($null -eq $gpuUtil -or $u -gt $gpuUtil)) { $gpuUtil=$u }
                if ($null -ne $t -and ($null -eq $gpuTemp -or $t -gt $gpuTemp)) { $gpuTemp=$t }
                if ($null -ne $fan -and ($null -eq $gpuFan -or $fan -gt $gpuFan)) { $gpuFan=$fan }
                if ($null -ne $pw) {
                    if ($null -eq $gpuPower) { $gpuPower = [double]$pw }
                    else { $gpuPower += [double]$pw }
                }
                if ($null -ne $mu) { $gpuMemUsed += $mu }
                if ($null -ne $mt) { $gpuMemTotal += $mt }
            }
        }
    } catch {}
    $read=0; $write=0
    try {
        $c = Get-Counter '\PhysicalDisk(_Total)\Disk Read Bytes/sec','\PhysicalDisk(_Total)\Disk Write Bytes/sec' -ErrorAction Stop
        $read=[math]::Round($c.CounterSamples[0].CookedValue/1MB,2); $write=[math]::Round($c.CounterSamples[1].CookedValue/1MB,2)
    } catch {}
    $gpuUtilCsv = if ($null -eq $gpuUtil) { "" } else { [math]::Round([double]$gpuUtil,2) }
    $gpuTempCsv = if ($null -eq $gpuTemp) { "" } else { [math]::Round([double]$gpuTemp,2) }
    $gpuFanCsv = if ($null -eq $gpuFan) { "" } else { [math]::Round([double]$gpuFan,2) }
    $gpuPowerCsv = if ($null -eq $gpuPower) { "" } else { [math]::Round([double]$gpuPower,2) }
    $cpuPowerCsv = if ($null -eq $cpuPower) { "" } else { [math]::Round([double]$cpuPower,2) }
    $cpuPowerLimitCsv = if ($null -eq $cpuPowerLimitPercent) { "" } else { [math]::Round([double]$cpuPowerLimitPercent,2) }
    Add-Content -Path $MonitorCsv -Value ("$ts,$Phase,$cpu,$clock,$maxClock,$memUsedPct,$memUsedGB,$memTotalGB,$temp,$($cpuTelemetry.TempSensor),$cpuPowerCsv,$($cpuTelemetry.PowerSensor),$cpuPowerLimitCsv,$($cpuTelemetry.PowerLimitSensor),$gpuCount,$gpuUtilCsv,$gpuTempCsv,$gpuFanCsv,$gpuPowerCsv,$gpuMemUsed,$gpuMemTotal,$read,$write") -Encoding UTF8
    Write-GpuSmiSample
}
function Start-FurMarkStress([int]$DurationSeconds) {
    $script:GpuTestStart = Get-Date
    $script:GpuSkipImmediate = $false

    if (!(Has-NvidiaGpu)) {
        $script:GpuTestStatus = "Not Tested"
        $script:GpuTestReason = "未检测到 NVIDIA GPU"
        $script:GpuTestEnd = Get-Date
        $script:GpuActualSeconds = 0
        $script:GpuSkipImmediate = $true
        Stage-Message "[跳过] 未检测到 NVIDIA GPU，跳过GPU压力测试"`n    Log "[GPU] 未检测到 NVIDIA GPU，立即跳过 GPU 压测。"
        return @()
    }

    $script:GpuTestStatus = "Running"
    $roots = @($ToolRoot,$LocalFurMark2Dir,$ReportBase,"C:\Program Files","C:\Program Files (x86)")
    $exe = Find-Exe @("furmark.exe","FurMark.exe","FurMark2.exe","furmark2.exe") $roots
    if (!$exe -and $UseOfficialFurMark2 -and $AutoDownloadFurMark2) { $exe = Install-ZipTool "FurMark2" $LocalFurMark2Dir @("furmark.exe","FurMark.exe","FurMark2.exe","furmark2.exe") (@($FurMark2Url)+$FurMark2FallbackUrls) }
    Add-ToolInfo "GPU stress" "FurMark 2" $exe "furmark-gl / 1920x1080 / max-time=$DurationSeconds / no-score-box / log-gpu-data" $FurMark2OfficialSource
    if (!$exe) { $script:GpuTestStatus = "Not Tested"; $script:GpuTestReason = "FurMark2 not found"; $script:GpuTestEnd = Get-Date; $script:GpuActualSeconds = 0; Log "[GPU] FurMark2 executable not found. GPU phase not tested."; return @() }
    $gpuDir = Join-Path $ReportRoot "furmark_gpu_log"; New-Item -ItemType Directory -Force -Path $gpuDir | Out-Null
    if ([string]::IsNullOrWhiteSpace($FurMarkArgs)) { $args = "--demo furmark-gl --width 1920 --height 1080 --max-time $DurationSeconds --no-score-box --log-gpu-data --export-dir `"$gpuDir`"" } else { $args = $FurMarkArgs -replace '<seconds>',$DurationSeconds }
    Log "[START] FurMark2: `"$exe`" $args"
    try { $p = Start-Process -FilePath $exe -ArgumentList $args -PassThru; Log "[PID] FurMark2 PID=$($p.Id)"; return @($p) } catch { $script:GpuTestStatus = "Not Tested"; $script:GpuTestReason = "FurMark2 start failed"; $script:GpuTestEnd = Get-Date; $script:GpuActualSeconds = 0; Log "[ERROR] FurMark2 start failed: $($_.Exception.Message)"; return @() }
}
function Write-WorkerScripts {
@'
param([int]$GB=1,[int]$Seconds=60,[string]$LogPath="")
$blocks = New-Object System.Collections.ArrayList
$end = (Get-Date).AddSeconds($Seconds)
function WLog($m){ if($LogPath){ Add-Content -Path $LogPath -Value ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"),$m) -Encoding UTF8 } }
try {
  $mb = [Math]::Max(1,$GB*1024)
  WLog "memory worker start targetGB=$GB targetMB=$mb seconds=$Seconds"
  for($i=0; $i -lt $mb; $i+=128){
    $size = 128MB
    $buf = New-Object byte[] $size
    for($j=0; $j -lt $buf.Length; $j+=4096){ $buf[$j] = 1 }
    [void]$blocks.Add($buf)
    if(($i % 1024) -eq 0){ WLog "allocatedMB=$i" }
    Start-Sleep -Milliseconds 10
  }
  WLog "memory worker allocated blocks=$($blocks.Count)"
  while((Get-Date) -lt $end){ Start-Sleep -Seconds 1 }
} catch {
  WLog "memory worker error: $($_.Exception.Message)"
  while((Get-Date) -lt $end){ Start-Sleep -Seconds 1 }
}
WLog "memory worker exit"
'@ | Out-File $MemoryWorkerPs1 -Encoding UTF8
@'
param([int]$Seconds=60,[int]$LoadPercent=100)
$end=(Get-Date).AddSeconds($Seconds)
$busy=[Math]::Max(1,[Math]::Min(100,$LoadPercent))
while((Get-Date) -lt $end){
  $sw=[Diagnostics.Stopwatch]::StartNew()
  while($sw.ElapsedMilliseconds -lt $busy){ [Math]::Sqrt(123456.789) | Out-Null }
  if($busy -lt 100){ Start-Sleep -Milliseconds (100-$busy) }
}
'@ | Out-File $CpuBurnerPs1 -Encoding UTF8
}
function Get-MemoryTargetGB {
    if ($MemoryStressGB -gt 0) { return $MemoryStressGB }
    if ($MemoryStressPercent -gt 0) {
        try { $cs=Get-CimInstance Win32_ComputerSystem; return [int][math]::Floor(($cs.TotalPhysicalMemory/1GB)*($MemoryStressPercent/100.0)) } catch { return 0 }
    }
    return 0
}
function Start-CpuBurners([int]$DurationSeconds) {
    Write-WorkerScripts
    $procs=@(); $threads=1
    try { $threads = [int](Get-CimInstance Win32_Processor | Measure-Object NumberOfLogicalProcessors -Sum).Sum } catch { $threads=4 }
    $threads = [Math]::Max(1,[Math]::Min($threads,128))
    for($i=0;$i -lt $threads;$i++) { $procs += Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$CpuBurnerPs1`" -Seconds $DurationSeconds -LoadPercent $CpuBurnerLoadPercent" -PassThru -WindowStyle Hidden }
    Log "[CPU] Built-in CPU burner started: workers=$threads load=$CpuBurnerLoadPercent%"
    # y-cruncher fallback: add memory pressure so CPU fallback also covers memory validation.
    # When y-cruncher is blocked by AppLocker/WDAC, do not rely on normal MemoryStressPercent.
    # Use the same physical RAM policy as y-cruncher fallback target (default 80%).
    try {
        $fallbackMemoryTargetGB = 0
        try {
            $cs = Get-CimInstance Win32_ComputerSystem
            $fallbackMemoryTargetGB = [math]::Max(1, [math]::Floor(($cs.TotalPhysicalMemory / 1GB) * ($YCruncherMemoryPercent / 100.0)))
        } catch {}

        if ($fallbackMemoryTargetGB -le 0) {
            $fallbackMemoryTargetGB = Get-MemoryTargetGB
        }

        if ($fallbackMemoryTargetGB -gt 0) {
            $mem = @(Start-MemoryWorkers -DurationSeconds $DurationSeconds -OverrideTargetGB $fallbackMemoryTargetGB)
            if ($mem.Count -gt 0) {
                $procs += $mem
                Log "[MEM] Fallback memory workers started: target=${fallbackMemoryTargetGB}GB policy=${YCruncherMemoryPercent}%"
            } else {
                Log "[WARN] Fallback memory target calculated but workers did not start."
            }
        } else {
            Log "[WARN] Fallback memory target unavailable."
        }
    } catch {
        Log "[WARN] Fallback memory workers failed: $($_.Exception.Message)"
    }
    return $procs
}
function Start-MemoryWorkers([int]$DurationSeconds, [int]$OverrideTargetGB=0) {
    Write-WorkerScripts
    $procs=@(); $target=if($OverrideTargetGB -gt 0){$OverrideTargetGB}else{Get-MemoryTargetGB}
    if ($target -le 0) { return @() }
    try {
        $os=Get-CimInstance Win32_OperatingSystem
        $totalGB=[math]::Floor(([double]$os.TotalVisibleMemorySize)/1MB)
        $freeGB=[math]::Floor(([double]$os.FreePhysicalMemory)/1MB)
        $safeGB=[math]::Max(1, $freeGB - $MemoryReserveGB)
        if ($target -gt $safeGB) { Log "[MEM] Target ${target}GB reduced to safe available ${safeGB}GB (reserve=${MemoryReserveGB}GB)"; $target=$safeGB }
    } catch {}
    $workers=[Math]::Max(1,$MemoryStressWorkers)
    $per=[Math]::Max(1,[Math]::Floor($target/$workers))
    $logPath = Join-Path $LogDir "memory_workers_detail.log"
    for($i=0;$i -lt $workers;$i++) { $procs += Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$MemoryWorkerPs1`" -GB $per -Seconds $DurationSeconds -LogPath `"$logPath`"" -PassThru -WindowStyle Hidden }
    Log "[MEM] Memory workers started: target=${target}GB workers=$workers perWorker=${per}GB reserve=${MemoryReserveGB}GB"
    return $procs
}

function Resolve-YCruncherBackend([string]$YCruncherRoot,[string]$DefaultExe) {
    # v90 add: explicit backend selection for newer CPU platforms.
    # Avoid relying on y-cruncher launcher auto-detection on some new server CPUs.
    $cpuName = ""
    try {
        $cpuName = (Get-CimInstance Win32_Processor |
            Select-Object -First 1 -ExpandProperty Name)
    } catch {}

    $binaryDir = Join-Path $YCruncherRoot "Binaries"

    if ($cpuName -match "EPYC 95|EPYC 97|Zen 5|9950|9900") {
        $zen5 = Join-Path $binaryDir "24-ZN5 ~ Komari.exe"
        if (Test-Path $zen5) {
            Log "[YCRUNCHER] CPU detected: $cpuName"
            Log "[YCRUNCHER] Using Zen5 backend: $zen5"
            return $zen5
        }
    }

    # v90 add: AMD Zen4 backend selection.
    # EPYC 9004 (Genoa) / Ryzen 7000 family use the Zen4 binary when available.
    if ($cpuName -match "EPYC 9[0-4]|EPYC 97|Zen 4|7950|7900|7700|7600") {
        $zen4 = Join-Path $binaryDir "22-ZN4 ~ Kizuna.exe"
        if (Test-Path $zen4) {
            Log "[YCRUNCHER] CPU detected: $cpuName"
            Log "[YCRUNCHER] Using Zen4 backend: $zen4"
            return $zen4
        }
    }

    Log "[YCRUNCHER] CPU detected: $cpuName"
    Log "[YCRUNCHER] Using default backend: $DefaultExe"
    return $DefaultExe
}

function Start-YCruncher([int]$DurationSeconds) {
    $roots=@($ToolRoot,$LocalYCruncherDir,$ReportBase)
    $exe=Find-Exe @("y-cruncher.exe") $roots
    if (!$exe -and $AutoDownloadYCruncher) { $exe=Install-ZipTool "y-cruncher" $LocalYCruncherDir @("y-cruncher.exe") (@($YCruncherUrl)+$YCruncherFallbackUrls) }
    if ($exe) {
        $backendExe = Resolve-YCruncherBackend (Split-Path $exe -Parent) $exe
        if ($backendExe) { $exe = $backendExe }
    }
    Add-ToolInfo "CPU + memory stress" "y-cruncher" $exe "stress / TL=$DurationSeconds / memory target by script" $YCruncherOfficialSource
    if (!$exe) { Log "[WARN] y-cruncher not found. Use custom fallback."; return @() }
    [void](Ensure-VCRuntime)
    # CPU phase: y-cruncher is the only CPU+memory workload.
    # Memory target is controlled directly by y-cruncher -M parameter.
    $targetGB = 0
    try {
        $cs = Get-CimInstance Win32_ComputerSystem
        $totalGB = [math]::Floor(($cs.TotalPhysicalMemory / 1GB))
        $targetGB = [math]::Max(1, [math]::Floor($totalGB * ($YCruncherMemoryPercent / 100.0)))
    } catch {
        $targetGB = Get-MemoryTargetGB
    }

    $targetBytes=[int64]($targetGB*1GB)
    if ($targetBytes -le 0) { $targetBytes=[int64](1GB) }

    Log "[YCRUNCHER] CPU mode memory target=${targetGB}GB (${YCruncherMemoryPercent}% physical RAM policy)"
    $argText = "pause:-2 skip-warnings stress -M:$targetBytes -D:60 -TL:$DurationSeconds"
    Log "[START] y-cruncher: `"$exe`" $argText"
    try { $p=Start-Process -FilePath $exe -ArgumentList $argText -PassThru; return @($p) } catch { Log "[ERROR] y-cruncher start failed: $($_.Exception.Message)"; return @() }
}
function Cleanup-DiskSpdTempFiles([string]$Reason) {
    if (!$CleanupDiskSpdTempFiles) { return }
    $candidates = @()

    # Always include files created by this run.
    foreach($f in @($script:DiskSpdTempFiles)) {
        if (![string]::IsNullOrWhiteSpace($f)) { $candidates += $f }
    }

    # v60: adaptive cleanup. Always clean files created by this run, plus resolved test drives.
    # When CleanupAllFixedDrives is enabled, scan every local fixed drive (C:/D:/E:/RAID volumes),
    # not only a hard-coded current machine layout. Removable/network drives are avoided.
    $cleanupDrives = @()
    if ($CleanupAllFixedDrives) {
        try {
            $cleanupDrives += @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" -ErrorAction SilentlyContinue |
                Where-Object { $_.DeviceID -match '^[A-Z]:' } |
                Sort-Object DeviceID |
                ForEach-Object { $_.DeviceID.ToUpper() })
        } catch {}
    }
    foreach($d in @($script:ResolvedTestDrives)) {
        if ($d -match '^[A-Za-z]:$') { $cleanupDrives += $d.ToUpper() }
    }
    $cleanupDrives = @($cleanupDrives | Where-Object { $_ } | Select-Object -Unique)

    foreach($d in $cleanupDrives) {
        try {
            $root = $d + "\"
            if (Test-Path $root) {
                Get-ChildItem -Path $root -Filter "diskspd_stress_*.dat" -File -ErrorAction SilentlyContinue |
                    ForEach-Object { $candidates += $_.FullName }
            }
        } catch {
            Log "[WARN] DiskSpd cleanup scan skipped on $d : $($_.Exception.Message)"
        }
    }

    $candidates = @($candidates | Where-Object { $_ } | Select-Object -Unique)
    foreach($f in $candidates) {
        try {
            if (Test-Path $f) {
                Remove-Item -LiteralPath $f -Force -ErrorAction Stop
                Log "[CLEANUP] Removed DiskSpd temp file ($Reason): $f"
            }
        } catch {
            Log "[WARN] Failed to remove DiskSpd temp file ($Reason): $f ; $($_.Exception.Message)"
        }
    }
    $script:DiskSpdTempFiles = @()
}
function Start-DiskSpdWorkload([int]$DurationSeconds,[string]$PhaseName,[ValidateSet("stability","throughput")][string]$WorkloadKind) {
    $roots=@($ToolRoot,$LocalDiskSpdDir,$ReportBase)
    $exe=Find-Exe @("diskspd.exe") $roots
    if (!$exe -and $AutoDownloadDiskSpd) { $exe=Install-ZipTool "DiskSpd" $LocalDiskSpdDir @("diskspd.exe") (@($DiskSpdUrl)+$DiskSpdFallbackUrls) }
    if (!$exe) { Log "[ERROR] DiskSpd not found. Disk phase skipped."; return @() }

    if($WorkloadKind -eq "throughput") {
        $argTemplate = "-c{0} -d{1} -w30 -t2 -o16 -b1M -Sh -si -L `"{2}`""
        $evidence = "interlocked sequential 1M mixed read/write throughput probe; MB/s reference evidence"
    } else {
        $argTemplate = "-c{0} -d{1} -r -w30 -t4 -o8 -b4K -L `"{2}`""
        $evidence = "4K random mixed stability workload; judged mainly by errors/IOPS/latency"
    }
    Add-ToolInfo "    " "DiskSpd-$WorkloadKind" $exe ($argTemplate -f $DiskFileSize,$DurationSeconds,"<testfile>") $DiskSpdOfficialSource

    $procs=@()
    foreach($d in $script:ResolvedTestDrives) {
        $di = Get-DiskDriveThresholdInfo $d
        $file=Join-Path ($d + "\") ("diskspd_stress_{0}_{1}_{2}.dat" -f $PhaseName,$WorkloadKind,$Stamp)
        $script:DiskSpdTempFiles += $file
        $args=($argTemplate -f $DiskFileSize,$DurationSeconds,$file)
        $outLog = Join-Path $LogDir ("diskspd_{0}_{1}.out.log" -f $WorkloadKind,$d.TrimEnd(':'))
        $errLog = Join-Path $LogDir ("diskspd_{0}_{1}.err.log" -f $WorkloadKind,$d.TrimEnd(':'))
        Log ("[START] DiskSpd {0} {1} [{2}; minimum>={3}MB/s; reference>={4}MB/s] {5} : `"{6}`" {7}" -f $WorkloadKind,$d,$di.Profile,$di.FailMBps,$di.PassMBps,$evidence,$exe,$args)
        try {
            $proc = Start-Process -FilePath $exe -ArgumentList $args -PassThru -RedirectStandardOutput $outLog -RedirectStandardError $errLog
            $proc | Add-Member -NotePropertyName DiskDrive -NotePropertyValue $d -Force
            $proc | Add-Member -NotePropertyName DiskWorkloadKind -NotePropertyValue $WorkloadKind -Force
            $proc | Add-Member -NotePropertyName DiskOutLog -NotePropertyValue $outLog -Force
            $proc | Add-Member -NotePropertyName DiskErrLog -NotePropertyValue $errLog -Force
            $procs += $proc
        } catch {
            ("ERROR: DiskSpd {0} start failed on {1}: {2}" -f $WorkloadKind,$d,$_.Exception.Message) | Out-File -FilePath $errLog -Encoding UTF8 -Append
            Log "[ERROR] DiskSpd $WorkloadKind start failed on $d : $($_.Exception.Message)"
        }
    }
    return $procs
}
function Get-DiskBothSplitDurations([int]$TotalDiskSeconds) {
    if($TotalDiskSeconds -le 0){ return [pscustomobject]@{StabilitySeconds=0;ThroughputSeconds=0;Policy="none"} }
    if($DiskIoProfile -eq "both" -and $DiskBothTimePolicy -eq "split") {
        $throughputSeconds = [int][math]::Floor($TotalDiskSeconds / 2)
        $stabilitySeconds = $TotalDiskSeconds - $throughputSeconds
        if($stabilitySeconds -lt 1 -and $TotalDiskSeconds -gt 0){ $stabilitySeconds = 1; $throughputSeconds = [math]::Max(0,$TotalDiskSeconds-1) }
        return [pscustomobject]@{StabilitySeconds=$stabilitySeconds;ThroughputSeconds=$throughputSeconds;Policy="split"}
    }
    return [pscustomobject]@{StabilitySeconds=$TotalDiskSeconds;ThroughputSeconds=$DiskThroughputProbeSeconds;Policy="append"}
}
function Start-DiskStress([int]$DurationSeconds,[string]$PhaseName) {
    Cleanup-DiskSpdTempFiles "before disk phase"
    $kind = if($DiskIoProfile -eq "throughput") { "throughput" } else { "stability" }
    return (Start-DiskSpdWorkload $DurationSeconds $PhaseName $kind)
}
function Invoke-DiskThroughputProbeIfNeeded([int]$OverrideSeconds=0) {
    if($script:SkipDiskPhase){ return }
    if($DiskIoProfile -ne "both"){ return }
    $effectiveSeconds = if($OverrideSeconds -gt 0){ $OverrideSeconds } else { $DiskThroughputProbeSeconds }
    if($effectiveSeconds -le 0){ return }
    Log "============================================================"
    Log ("[PHASE START] disk-throughput-probe DurationSeconds={0} DISK=True Policy={1}" -f $effectiveSeconds,$DiskBothTimePolicy)
    Log "============================================================"
    $script:DiskModuleAttempted = $true
    $procs = @(Start-DiskSpdWorkload $effectiveSeconds "throughput_probe" "throughput")
    if($procs.Count -gt 0){
        $script:DiskModuleExecuted = $true
        $script:DiskModuleReason = ""
    } elseif(!$script:DiskModuleExecuted) {
        $script:DiskModuleReason = "DiskSpd 顺序读写测试未成功启动"
    }
    $end=(Get-Date).AddSeconds($effectiveSeconds)
    while((Get-Date) -lt $end) { Write-MonitorSample "disk-throughput-probe"; Start-Sleep -Seconds $IntervalSeconds }
    Write-MonitorSample "disk-throughput-probe"
    Wait-DiskSpdFlush $procs 180
    Stop-Procs $procs
    Cleanup-DiskSpdTempFiles "after disk throughput probe"
    Log "[PHASE END] disk-throughput-probe"
}
function Get-ProcessExitCodeSafe($Process) {
    $result = [ordered]@{
        Available = $false
        ExitCode = $null
        Error = ""
    }
    if($null -eq $Process){
        $result.Error = "Process object is null"
        return [pscustomobject]$result
    }
    try {
        # Required when Start-Process uses redirected stdout/stderr. This also
        # allows .NET to complete stream flushing before ExitCode is queried.
        $Process.WaitForExit()
        $Process.Refresh()
        $rawExitCode = $Process.ExitCode
        if($null -ne $rawExitCode -and -not [string]::IsNullOrWhiteSpace([string]$rawExitCode) -and ([string]$rawExitCode -match '^-?\d+$')){
            $result.Available = $true
            $result.ExitCode = [int]$rawExitCode
        } else {
            $result.Error = "ExitCode was unavailable"
        }
    } catch {
        $result.Error = $_.Exception.Message
    }
    return [pscustomobject]$result
}
function Wait-DiskSpdFlush($Processes,[int]$TimeoutSeconds=180) {
    $diskProcs=@()
    foreach($p in @($Processes)) {
        try {
            if($p -and $p.ProcessName -match "diskspd") { $diskProcs += $p }
        } catch {}
    }
    if($diskProcs.Count -eq 0){ return }
    Log ("[DISKSPD] Waiting up to {0}s for DiskSpd to exit and flush stdout logs..." -f $TimeoutSeconds)
    $deadline=(Get-Date).AddSeconds($TimeoutSeconds)
    while((Get-Date) -lt $deadline) {
        $alive=@()
        foreach($p in $diskProcs) {
            try { $p.Refresh(); if(!$p.HasExited){ $alive += $p } } catch {}
        }
        if($alive.Count -eq 0){
            foreach($p in $diskProcs){
                try {
                    $driveText = if($p.PSObject.Properties["DiskDrive"]){$p.DiskDrive}else{"?"}
                    $kindText = if($p.PSObject.Properties["DiskWorkloadKind"]){$p.DiskWorkloadKind}else{"?"}
                    $exitInfo = Get-ProcessExitCodeSafe $p
                    $exitText = if($exitInfo.Available){[string]$exitInfo.ExitCode}else{"Unavailable"}
                    Log ("[DISKSPD EXIT] PID={0}; Drive={1}; Kind={2}; ExitCode={3}" -f $p.Id,$driveText,$kindText,$exitText)

                    if($exitInfo.Available){
                        if([int]$exitInfo.ExitCode -ne 0 -and $p.PSObject.Properties["DiskErrLog"]){
                            ("ERROR: DiskSpd exited with code {0}; Drive={1}; Workload={2}" -f $exitInfo.ExitCode,$driveText,$kindText) | Out-File -FilePath $p.DiskErrLog -Encoding UTF8 -Append
                        }
                    } else {
                        # A missing ExitCode is not proof of workload failure. The report
                        # will use the output log/result markers and parsed measurements.
                        $outLogText = if($p.PSObject.Properties["DiskOutLog"]){$p.DiskOutLog}else{""}
                        $hasOutput = $false
                        if(-not [string]::IsNullOrWhiteSpace($outLogText) -and (Test-Path -LiteralPath $outLogText)){
                            try { $hasOutput = ((Get-Item -LiteralPath $outLogText -ErrorAction Stop).Length -gt 0) } catch {}
                        }
                        Log ("[WARN] DiskSpd ExitCode unavailable; Drive={0}; Workload={1}; OutputPresent={2}; report will evaluate the captured result log. Detail={3}" -f $driveText,$kindText,$hasOutput,$exitInfo.Error)
                    }
                } catch {
                    Log ("[WARN] DiskSpd exit-status inspection failed: {0}" -f $_.Exception.Message)
                }
            }
            Log "[DISKSPD] All DiskSpd processes exited."
            return
        }
        Start-Sleep -Seconds 2
    }
    foreach($p in $diskProcs){
        try {
            $p.Refresh()
            if(!$p.HasExited -and $p.PSObject.Properties["DiskErrLog"]){
                ("ERROR: DiskSpd timed out before result flush; PID={0}; Drive={1}; Workload={2}" -f $p.Id,$p.DiskDrive,$p.DiskWorkloadKind) | Out-File -FilePath $p.DiskErrLog -Encoding UTF8 -Append
            }
        } catch {}
    }
    Log "[WARN] DiskSpd flush wait timeout; remaining DiskSpd processes will be stopped."
}
function Stop-ProcessTree([int]$ProcessId) {
    try {
        $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$ProcessId" -ErrorAction SilentlyContinue
        foreach($child in @($children)) {
            Stop-ProcessTree ([int]$child.ProcessId)
        }
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    } catch {}
}

function Stop-YCruncherGracefully([int]$WaitSeconds=10) {
    $yc=@(Get-Process -Name "y-cruncher" -ErrorAction SilentlyContinue)
    if ($yc.Count -eq 0) { return }

    Log "[YCRUNCHER] Graceful shutdown requested. Waiting ${WaitSeconds}s before force cleanup."

    foreach($p in $yc) {
        try {
            if(!$p.HasExited) {
                # First try normal application close.
                [void]$p.CloseMainWindow()
            }
        } catch {}
    }

    $deadline=(Get-Date).AddSeconds($WaitSeconds)
    while((Get-Date) -lt $deadline) {
        $alive=@(Get-Process -Name "y-cruncher" -ErrorAction SilentlyContinue)
        if($alive.Count -eq 0) {
            Log "[YCRUNCHER] Exited normally after shutdown request."
            return
        }
        Start-Sleep -Seconds 1
    }

    Log "[YCRUNCHER] Graceful shutdown timeout. Force stopping remaining process tree."
    foreach($p in @(Get-Process -Name "y-cruncher" -ErrorAction SilentlyContinue)) {
        try { Stop-ProcessTree ([int]$p.Id) } catch {}
    }
}

function Stop-Procs($Processes) {
    foreach($p in $Processes) {
        try {
            if ($p -and !$p.HasExited) {
                if ($p.ProcessName -eq "y-cruncher") {
                    Log "[CLEANUP] Graceful stopping y-cruncher PID=$($p.Id)"
                    Stop-YCruncherGracefully 10
                }
                else {
                    Log "[CLEANUP] Stopping process tree PID=$($p.Id) Name=$($p.ProcessName)"
                    Stop-ProcessTree ([int]$p.Id)
                }
            }
        } catch {}
    }

    # Cleanup orphaned benchmark processes, especially y-cruncher child processes.
    foreach($n in @("y-cruncher","furmark","FurMark","FurMark2","diskspd")) {
        Get-Process -Name $n -ErrorAction SilentlyContinue | ForEach-Object {
            try {
                Log "[CLEANUP] Force stopping leftover process Name=$($_.ProcessName) PID=$($_.Id)"
                Stop-ProcessTree ([int]$_.Id)
            } catch {}
        }
    }

    Start-Sleep -Seconds 2
}
function Run-Phase([string]$Phase,[int]$DurationSeconds,[bool]$RunGpu,[bool]$RunCpu,[bool]$RunDisk) {
    if ($DurationSeconds -le 0) { Log "[SKIP] Phase=$Phase DurationSeconds=$DurationSeconds"; return }
    Log "============================================================"
    if($RunGpu){Stage-Message "[运行] GPU压力测试开始"}
    if($RunCpu){Stage-Message "[运行] CPU+内存压力测试开始"}
    if($RunDisk){Stage-Message "[运行] 磁盘压力测试开始"}
    Log "[PHASE START] $Phase DurationSeconds=$DurationSeconds GPU=$RunGpu CPU=$RunCpu DISK=$RunDisk"
    Log "============================================================"
    $procs=@()
    if ($RunGpu) {
        $gpuProcs = @(Start-FurMarkStress $DurationSeconds)
        if ($gpuProcs.Count -gt 0) {
            $procs += $gpuProcs
            Start-Sleep -Seconds 3
        } elseif ($script:GpuSkipImmediate -and !$RunCpu -and !$RunDisk) {
            Log "[PHASE SKIP] $Phase only requested GPU, but no NVIDIA GPU was detected. Skip immediately."
            return
        }
    }
    if ($RunCpu) {
        $script:CpuModuleAttempted = $true
        $script:CpuModuleReason = ""
        $script:CpuMemBackendUsed = "Unknown"
        $script:CpuMemBackendReason = ""
        $script:CpuMemMemoryPolicy = "$YCruncherMemoryPercent% RAM policy"
        $memoryWorkersStarted = $false
        if ($CpuMemBackend -eq "ycruncher") {
            $yc = @(Start-YCruncher $DurationSeconds)
            $procs += $yc
            if ($yc.Count -gt 0) {
                $script:CpuMemBackendUsed = "y-cruncher"
            }
            # y-cruncher handles CPU and memory pressure directly. No MemoryWorkers in CPU phase.
            if ($yc.Count -eq 0) {
                $procs += Start-CpuBurners $DurationSeconds
                if (!$memoryWorkersStarted) { $procs += Start-MemoryWorkers $DurationSeconds; $memoryWorkersStarted = $true }
            }
            elseif ($AutoFallbackCustomCpuMem) {
                # Dynamic fallback check:
                # Large NUMA servers (EPYC/Xeon, >128 logical processors) need more time
                # for y-cruncher memory allocation and topology initialization.
                $logicalCpu = (Get-CimInstance Win32_ComputerSystem -ErrorAction SilentlyContinue).NumberOfLogicalProcessors
                if (!$logicalCpu) { $logicalCpu = 32 }

                $dynamicWait = if ($logicalCpu -gt 128) {
                    180
                } elseif ($logicalCpu -gt 32) {
                    90
                } else {
                    30
                }

                # Fallback detection wait must not consume the CPU phase duration.
                # Previous logic could consume almost the entire short test duration
                # (for example 180s test -> 170s wait -> only 10s fallback workload).
                # Keep detection time bounded and leave enough time for fallback validation.
                $wait=[math]::Max(10,[math]::Min($dynamicWait,60))
                if ($DurationSeconds -le 30) {
                    $wait=[math]::Max(5,[math]::Floor($DurationSeconds/3))
                }

                $ycProc = Get-Process -Name "y-cruncher" -ErrorAction SilentlyContinue
                $beforeMemory = 0
                if ($ycProc) {
                    $beforeMemory = $ycProc.WorkingSet64
                }

                Log "[YCRUNCHER] Fallback check logicalCPU=${logicalCpu}; wait=${wait}s threshold=${CpuFallbackLoadThresholdPercent}%"
                Start-Sleep -Seconds $wait

                $ycProcAfter = Get-Process -Name "y-cruncher" -ErrorAction SilentlyContinue
                $afterMemory = 0
                $ycThreads = 0
                if ($ycProcAfter) {
                    $afterMemory = $ycProcAfter.WorkingSet64
                    $ycThreads = $ycProcAfter.Threads.Count
                }

                $memoryGrowthMB = [math]::Round(($afterMemory-$beforeMemory)/1MB,2)
                $load=Get-CurrentCpuLoadPercent

                Log "[YCRUNCHER] Check CPU=${load}% Threads=${ycThreads} MemoryGrowthMB=${memoryGrowthMB}"

                # Only fallback when y-cruncher appears inactive:
                # process missing + no memory growth + low CPU.
                if (!$ycProcAfter -or (($memoryGrowthMB -le 0) -and ($load -ge 0 -and $load -lt $CpuFallbackLoadThresholdPercent))) {
                    Log "[FALLBACK] y-cruncher inactive detected. Starting built-in CPU burner."
                    $script:CpuMemBackendUsed = "Fallback CPU+Memory Worker"
                    $script:CpuMemBackendReason = "y-cruncher inactive or failed to enter stress state"
                    # Fallback takeover must not shorten the CPU phase.
                    # DurationSeconds is the configured CPU phase duration.
                    # The phase timer below controls the real end time; fallback workers
                    # should run from activation until that phase end.
                    Log "[FALLBACK] Starting CPU+MEM fallback workload. phaseDurationSeconds=${DurationSeconds}; detectionWaitSeconds=${wait}"
                    $procs += Start-CpuBurners $DurationSeconds
                } else {
                    Log "[YCRUNCHER] Activity detected. Skip fallback."
                }
            }
        } else { $procs += Start-CpuBurners $DurationSeconds; $procs += Start-MemoryWorkers $DurationSeconds }

        # A CPU module is considered tested only when a real workload process started.
        $cpuWorkloadProcesses = @($procs | Where-Object {
            try {
                $_ -and (
                    $_.ProcessName -match "powershell|y-cruncher|Komari|Kizuna|ZN[0-9]|SKX|NHM" -or
                    $script:CpuMemBackendUsed -eq "y-cruncher"
                )
            } catch { $false }
        })
        if($cpuWorkloadProcesses.Count -gt 0){
            $script:CpuModuleExecuted = $true
            $script:CpuModuleReason = ""
        } else {
            $script:CpuModuleExecuted = $false
            $script:CpuModuleReason = "CPU/内存压力程序未成功启动"
        }
    }
    if ($RunDisk -and !$script:SkipDiskPhase) {
        $script:DiskModuleAttempted = $true
        $script:DiskModuleReason = ""
        $diskPhaseProcs = @(Start-DiskStress $DurationSeconds $Phase)
        $procs += $diskPhaseProcs
        if($diskPhaseProcs.Count -gt 0){
            $script:DiskModuleExecuted = $true
        } else {
            $script:DiskModuleExecuted = $false
            $script:DiskModuleReason = "DiskSpd 未成功启动或没有可测试磁盘"
        }
    } elseif($RunDisk -and $script:SkipDiskPhase) {
        $script:DiskModuleAttempted = $true
        $script:DiskModuleExecuted = $false
        $script:DiskModuleReason = "磁盘阶段已跳过：没有满足条件的测试盘或可用空间不足"
    }
    if ($procs.Count -eq 0 -and !$RunDisk -and !$RunCpu) {
        Log "[PHASE SKIP] $Phase has no runnable workload. Skip monitoring loop immediately."
        return
    }
    $end=(Get-Date).AddSeconds($DurationSeconds)
    while((Get-Date) -lt $end) { Write-MonitorSample $Phase; Start-Sleep -Seconds $IntervalSeconds }
    Write-MonitorSample $Phase
    Log "[PHASE STOP] $Phase"
    if ($RunDisk) { Wait-DiskSpdFlush $procs 180 }
    Log "[PHASE CLEANUP] Cleaning workload processes after $Phase"
    Stop-Procs $procs
    if ($RunCpu) {
        $left = @(Get-Process -Name "y-cruncher" -ErrorAction SilentlyContinue)
        if ($left.Count -gt 0) {
            Log "[WARN] y-cruncher still running after cleanup. Final force cleanup."
            foreach($p in $left) { Stop-ProcessTree ([int]$p.Id) }
        } else {
            Log "[CPU] y-cruncher exited and CPU phase resources released."
        }
    }
    if ($RunGpu -and $script:GpuTestStatus -eq "Running") {
        $script:GpuTestStatus = "PASS"
        $script:GpuTestEnd = Get-Date
        try { $script:GpuActualSeconds = [int][math]::Round((New-TimeSpan -Start $script:GpuTestStart -End $script:GpuTestEnd).TotalSeconds) } catch { $script:GpuActualSeconds = 0 }
        $script:GpuTestReason = ""
    }
    if ($RunDisk) { Cleanup-DiskSpdTempFiles "after disk phase" }
    Start-Sleep -Seconds 5
}

function New-SvgChart([string]$Path,$Rows,[string]$Field,[string]$Title,[string]$Unit) {
    $vals=@(); $times=@()
    foreach($r in $Rows){
        $x=Num $r.$Field
        if($null -ne $x -and $x -ge 0){ $vals+=$x; $times += $r.Timestamp }
    }
    if($vals.Count -lt 2){ return }
    $w=980; $h=260; $padL=60; $padR=20; $padT=34; $padB=42
    $max=($vals|Measure-Object -Maximum).Maximum; if($max -le 0){$max=1}
    $avg=[math]::Round(($vals|Measure-Object -Average).Average,2)
    $pts=@()
    for($i=0;$i -lt $vals.Count;$i++){
        $x=$padL+($i*($w-$padL-$padR)/[math]::Max(1,$vals.Count-1))
        $y=$h-$padB-($vals[$i]*($h-$padT-$padB)/$max)
        $pts += ("{0:N1},{1:N1}" -f $x,$y)
    }
    $leftLabel=""; $rightLabel=""
    try { $leftLabel=([datetime]$times[0]).ToString('MM-dd HH:mm'); $rightLabel=([datetime]$times[-1]).ToString('MM-dd HH:mm') } catch {}
    $svg=@"
<svg xmlns="http://www.w3.org/2000/svg" width="$w" height="$h" viewBox="0 0 $w $h">
<rect x="0" y="0" width="$w" height="$h" fill="white" stroke="#d9dee7"/>
<text x="$padL" y="22" font-size="15" font-weight="700" font-family="Arial,Microsoft YaHei">$Title</text>
<text x="$($w-220)" y="22" font-size="12" font-family="Arial">Max: $([math]::Round($max,2))$Unit | Avg: $avg$Unit</text>
<line x1="$padL" y1="$padT" x2="$padL" y2="$($h-$padB)" stroke="#9ca3af"/>
<line x1="$padL" y1="$($h-$padB)" x2="$($w-$padR)" y2="$($h-$padB)" stroke="#9ca3af"/>
<text x="10" y="$padT" font-size="11" font-family="Arial">$([math]::Round($max,2))$Unit</text>
<text x="18" y="$($h-$padB)" font-size="11" font-family="Arial">0</text>
<polyline fill="none" stroke="#1f4e79" stroke-width="2" points="$($pts -join ' ')"/>
<text x="$padL" y="$($h-12)" font-size="11" font-family="Arial">$leftLabel</text>
<text x="$($w-110)" y="$($h-12)" font-size="11" font-family="Arial">$rightLabel</text>
</svg>
"@
    $svg | Out-File $Path -Encoding UTF8
}
function StatusBadge($s){
    if($s -eq "PASS"){ return "<span class='pass'>$($L.Pass)</span>" }
    if($s -eq "WARN"){ return "<span class='warn'>$($L.Warn)</span>" }
    if($s -eq "FAIL"){ return "<span class='fail'>$($L.Fail)</span>" }
    if($s -eq "NOT_TESTED"){ return "<span class='na'>$($L.NotTested)</span>" }
    if($s -eq "NOT_DETECTED"){ return "<span class='na'>$($L.NotDetected)</span>" }
    return "<span class='na'>$(Html $s)</span>"
}
function HtmlE([object]$v) {
    if($null -eq $v){ return "" }
    $s=[string]$v
    if($s -match "&#x[0-9A-Fa-f]+;"){
        $s=[System.Net.WebUtility]::HtmlDecode($s)
    }
    return (Html $s)
}

function HtmlListFromText([object]$v) {
    if($null -eq $v){ return "" }
    $s=[string]$v
    if($s -match "&#x[0-9A-Fa-f]+;"){
        $s=[System.Net.WebUtility]::HtmlDecode($s)
    }
    if([string]::IsNullOrWhiteSpace($s)){ return "" }
    $parts = @($s -split '\s*;\s*' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if($parts.Count -le 1){ return (HtmlE $s) }
    $lis = ($parts | ForEach-Object { "<li>$(HtmlE $_)</li>" }) -join ""
    return "<ul class='reason-list'>$lis</ul>"
}
function HtmlPipeList([object]$v) {
    if($null -eq $v){ return "" }
    $s=[string]$v
    if([string]::IsNullOrWhiteSpace($s)){ return "" }
    $parts = @($s -split '\s*\|\s*' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if($parts.Count -le 1){ return (HtmlE $s) }
    $lis = ($parts | ForEach-Object { "<li>$(HtmlE $_)</li>" }) -join ""
    return "<ul class='metric-list'>$lis</ul>"
}
function CriteriaCell([string]$pass,[string]$warn,[string]$fail) {
    return "<div class='criteria-grid'><div><div class='criteria-title pass'>通过条件</div>$pass</div><div><div class='criteria-title warn'>关注条件</div>$warn</div><div><div class='criteria-title fail'>不合格条件</div>$fail</div></div>"
}
function FmtVal($v,$unit="") { if($null -eq $v -or [string]::IsNullOrWhiteSpace([string]$v)){return "-"}; return ("$v $unit").Trim() }
function Get-MinTime($rows){ $arr=@(); foreach($r in $rows){ try{$arr += [datetime]$r.Timestamp}catch{} }; if($arr.Count -eq 0){return $null}; return ($arr|Sort-Object|Select-Object -First 1) }
function Get-MaxTime($rows){ $arr=@(); foreach($r in $rows){ try{$arr += [datetime]$r.Timestamp}catch{} }; if($arr.Count -eq 0){return $null}; return ($arr|Sort-Object|Select-Object -Last 1) }
function Stage-Row($name,$rows){
    $s=Get-MinTime $rows; $e=Get-MaxTime $rows
    if($null -eq $s -or $null -eq $e){ return "" }
    $min=[math]::Round((New-TimeSpan -Start $s -End $e).TotalMinutes,1)
    return "<tr><td>$(Html $name)</td><td>$($s.ToString('yyyy-MM-dd HH:mm:ss'))</td><td>$($e.ToString('yyyy-MM-dd HH:mm:ss'))</td><td>$min $($L.Minutes)</td></tr>"
}

function Get-StableRows($Rows,[int]$SkipStartSeconds,[int]$SkipEndSeconds){
    $arr=@($Rows)
    if($arr.Count -lt 6){ return $arr }
    $s=Get-MinTime $arr; $e=Get-MaxTime $arr
    if($null -eq $s -or $null -eq $e){ return $arr }
    $duration=(New-TimeSpan -Start $s -End $e).TotalSeconds
    if($duration -le ($SkipStartSeconds + $SkipEndSeconds + 30)){ return $arr }
    $fs=$s.AddSeconds($SkipStartSeconds); $fe=$e.AddSeconds(-1 * $SkipEndSeconds)
    $filtered=@($arr | Where-Object { try { $t=[datetime]$_.Timestamp; ($t -ge $fs -and $t -le $fe) } catch { $false } })
    if($filtered.Count -ge 3){ return $filtered }
    return $arr
}
function Get-GpuEffectiveRows($Rows){
    $arr=@($Rows)
    if($arr.Count -lt 3){ return $arr }
    $stable=@(Get-StableRows $arr $GpuStableSkipStartSeconds $GpuStableSkipEndSeconds)
    $effective=@($stable | Where-Object {
        $u=Num $_.GPU_Util_Max_Percent; $p=Num $_.GPU_Power_Total_W
        (($u -ne $null -and $u -ge $GpuEffectiveLoadMinPercent) -or ($p -ne $null -and $p -ge $GpuEffectivePowerMinW))
    })
    if($effective.Count -ge 3){ return $effective }
    if($stable.Count -ge 3){ return $stable }
    return $arr
}

function Merge-BaseReportNonDiskSamples {
    if(!$script:SupplementMergeMode){ return }
    if([string]::IsNullOrWhiteSpace($script:MergeBaseReportDir)){ return }
    $baseLogDir = Join-Path $script:MergeBaseReportDir "logs"
    $baseMonitor = Join-Path $baseLogDir "monitor.csv"
    if(!(Test-Path $baseMonitor)){ Log "[MERGE] Base monitor.csv not found: $baseMonitor"; return }
    if(!(Test-Path $MonitorCsv)){ Log "[MERGE] Current monitor.csv not found: $MonitorCsv"; return }
    try {
        $baseRows = @(Import-Csv $baseMonitor)
        $newRows  = @(Import-Csv $MonitorCsv)

        # v97: normalize old monitor.csv schemas before merging so new CPU power
        # columns are not dropped when supplementing a v96 base report.
        $newProps = @()
        if($newRows.Count -gt 0){ $newProps = @($newRows[0].PSObject.Properties.Name) }
        foreach($r in $baseRows){
            foreach($pname in $newProps){
                if(!($r.PSObject.Properties.Name -contains $pname)){
                    Add-Member -InputObject $r -NotePropertyName $pname -NotePropertyValue "" -Force
                }
            }
        }

        $baseKeep = @($baseRows | Where-Object { $_.Phase -ne "disk" })
        $newKeep  = @($newRows  | Where-Object { $_.Phase -eq "disk" -or $_.Phase -eq "all" })
        $merged = @($baseKeep + $newKeep | Sort-Object { try { [datetime]$_.Timestamp } catch { [datetime]::MinValue } })
        if($merged.Count -gt 0){ $merged | Export-Csv -Path $MonitorCsv -NoTypeInformation -Encoding UTF8 }
        Log ("[MERGE] monitor.csv merged. BaseNonDisk={0}; CurrentDisk={1}; Total={2}; Base={3}" -f $baseKeep.Count,$newKeep.Count,$merged.Count,$script:MergeBaseReportDir)
        foreach($name in @("gpu_smi.csv","cpu_sensors.csv")){
            $b = Join-Path $baseLogDir $name
            $c = Join-Path $LogDir $name
            if((Test-Path $b) -and (Test-Path $c)){
                try {
                    $bLines = @(Get-Content $b -ErrorAction SilentlyContinue)
                    $cLines = @(Get-Content $c -ErrorAction SilentlyContinue)
                    if($bLines.Count -gt 0){
                        $header = $bLines[0]
                        $body = @()
                        if($bLines.Count -gt 1){ $body += $bLines[1..($bLines.Count-1)] }
                        if($cLines.Count -gt 1){ $body += $cLines[1..($cLines.Count-1)] }
                        @($header) + $body | Out-File $c -Encoding UTF8
                    }
                } catch {}
            }
        }
    } catch {
        Log "[MERGE] Failed: $($_.Exception.Message)"
    }
}

function Get-DiskSpdParsedResult {
    $result=[ordered]@{TotalMiBps=$null;ReadMiBps=$null;WriteMiBps=$null;Iops=$null;AvgLatMs=$null;Files=0;Source="";Details=@()}
    $details=@()
    try{
        $files=@(Get-ChildItem -Path $LogDir -Filter "diskspd_*.out.log" -ErrorAction SilentlyContinue)
        if($files.Count -eq 0){ return [pscustomobject]$result }

        foreach($f in $files){
            $drive=""
            $kind='stability'
            if($f.Name -match '^diskspd_(stability|throughput)_([A-Za-z])\.out\.log$'){
                $kind=$Matches[1]
                $drive = ($Matches[2].ToUpper() + ':')
            } elseif($f.Name -match '^diskspd_([A-Za-z])\.out\.log$'){
                $drive = ($Matches[1].ToUpper() + ':')
            } else {
                Log "[DISKSPD PARSE] Ignore unrecognized log filename: $($f.Name)"
                continue
            }

            $fileTotal=$null
            $fileRead=$null
            $fileWrite=$null
            $fileIops=$null
            $fileLat=$null
            $parseOk=$false
            $parseReason=""
            try {
                $lines = @(Get-Content -Path $f.FullName -ErrorAction Stop)
                if($lines.Count -eq 0){
                    $parseReason = "结果日志为空"
                } else {
                    $totalRow = Get-DiskSpdSectionResult $lines "total"
                    $readRow = Get-DiskSpdSectionResult $lines "read"
                    $writeRow = Get-DiskSpdSectionResult $lines "write"
                    if($null -ne $totalRow){
                        $fileTotal = $totalRow.MiBps
                        $fileIops = $totalRow.Iops
                        $fileLat = $totalRow.AvgLatMs
                        if($null -ne $readRow){ $fileRead = $readRow.MiBps }
                        if($null -ne $writeRow){ $fileWrite = $writeRow.MiBps }
                        $parseOk = ($null -ne $fileTotal)
                    } else {
                        $parseReason = "未找到 DiskSpd total 汇总行"
                    }
                }
            } catch {
                $parseReason = $_.Exception.Message
            }

            if(!$parseOk -and [string]::IsNullOrWhiteSpace($parseReason)){
                $parseReason = "结果格式未识别"
            }
            if(!$parseOk){
                Log ("[DISKSPD PARSE WARN] Drive={0} Kind={1} File={2} Reason={3}" -f $drive,$kind,$f.Name,$parseReason)
            }

            $di = Get-DiskDriveThresholdInfo $drive
            $details += [pscustomobject]@{
                Drive = (Normalize-DriveLetter $drive)
                TotalMiBps = if($null -ne $fileTotal){[math]::Round([double]$fileTotal,2)}else{$null}
                ReadMiBps = if($null -ne $fileRead){[math]::Round([double]$fileRead,2)}else{$null}
                WriteMiBps = if($null -ne $fileWrite){[math]::Round([double]$fileWrite,2)}else{$null}
                Iops = if($null -ne $fileIops){[math]::Round([double]$fileIops,2)}else{$null}
                AvgLatMs = if($null -ne $fileLat){[math]::Round([double]$fileLat,3)}else{$null}
                Profile = $di.Profile
                PassMBps = $di.PassMBps
                FailMBps = $di.FailMBps
                IsSystemDrive = $di.IsSystemDrive
                Model = $di.Model
                LogFile = $f.Name
                WorkloadKind = $kind
                ParseOk = $parseOk
                ParseReason = $parseReason
            }
        }

        $preferredKind = if($DiskIoProfile -eq "throughput") { "throughput" } else { "stability" }
        $pref = @($details | Where-Object { $_.WorkloadKind -eq $preferredKind -and $_.ParseOk })
        if($pref.Count -gt 0){
            $total=0.0
            $read=0.0
            $write=0.0
            $iops=0.0
            $latMax=$null
            foreach($x in $pref){
                if($null -ne $x.TotalMiBps){$total += [double]$x.TotalMiBps}
                if($null -ne $x.ReadMiBps){$read += [double]$x.ReadMiBps}
                if($null -ne $x.WriteMiBps){$write += [double]$x.WriteMiBps}
                if($null -ne $x.Iops){$iops += [double]$x.Iops}
                if($null -ne $x.AvgLatMs){
                    if($null -eq $latMax -or [double]$x.AvgLatMs -gt $latMax){$latMax=[double]$x.AvgLatMs}
                }
            }
            $result.TotalMiBps=[math]::Round($total,2)
            $result.ReadMiBps=[math]::Round($read,2)
            $result.WriteMiBps=[math]::Round($write,2)
            $result.Iops=[math]::Round($iops,2)
            if($null -ne $latMax){$result.AvgLatMs=[math]::Round($latMax,3)}
            $result.Files=$pref.Count
            $result.Source=("DiskSpd {0} out.log" -f $preferredKind)
        }
        $result.Details=@($details)
    } catch {
        Log "[DISKSPD PARSE ERROR] $($_.Exception.Message)"
    }
    return [pscustomobject]$result
}
function Get-DiskSpdLogHealth([string]$Drive,[ValidateSet("stability","throughput")][string]$WorkloadKind) {
    $d = Normalize-DriveLetter $Drive
    $letter = $d.TrimEnd(':')
    $outLog = Join-Path $LogDir ("diskspd_{0}_{1}.out.log" -f $WorkloadKind,$letter)
    $errLog = Join-Path $LogDir ("diskspd_{0}_{1}.err.log" -f $WorkloadKind,$letter)
    $allLines = @()
    $warningLines = @()
    $outExists = Test-Path $outLog
    $outBytes = 0

    if($outExists){
        try { $outBytes = (Get-Item -LiteralPath $outLog -ErrorAction Stop).Length } catch {}
    }
    foreach($path in @($outLog,$errLog)){
        if(Test-Path $path){
            try {
                $lines = @(Get-Content -Path $path -ErrorAction SilentlyContinue)
                $allLines += $lines
                $warningLines += @($lines | Where-Object { $_ -match '(?i)^\s*WARNING\s*:' })
            } catch {}
        }
    }

    # Match explicit fatal I/O/startup failures only. Ordinary WARNING lines are retained as notes.
    # v95 could emit "ERROR: DiskSpd exited with code ; ..." when ExitCode was null.
    # That line does not prove a non-zero process exit and must not invalidate valid result output.
    $legacyBlankExitPattern = '(?i)^\s*ERROR\s*:\s*DiskSpd exited with code\s*;\s*Drive=.*;\s*Workload='
    $legacyBlankExitLines = @($allLines | Where-Object { $_ -match $legacyBlankExitPattern } | Select-Object -Unique)
    if($legacyBlankExitLines.Count -gt 0){
        $warningLines += @($legacyBlankExitLines | ForEach-Object { "WARNING: Ignored legacy v95 blank DiskSpd ExitCode pseudo-error; result log is evaluated instead." })
    }

    $fatalPattern = '(?i)^\s*(ERROR|FATAL)\s*:|error opening|failed to|failure opening|I/O error|input/output error|bad block|CRC error|data error|device is not ready|device does not exist|access is denied|not enough (disk )?space|disk full|timed out|timeout while'
    $fatalLines = @($allLines | Where-Object {
        $_ -match $fatalPattern -and
        $_ -notmatch '(?i)^\s*WARNING\s*:' -and
        $_ -notmatch $legacyBlankExitPattern
    } | Select-Object -Unique)
    $hasResultMarker = (@($allLines | Where-Object { $_ -match '(?i)Results for timespan|^\s*Total IO\s*$|^\s*total\s*:' }).Count -gt 0)

    return [pscustomobject]@{
        OutputExists = $outExists
        HasOutput = ($outExists -and $outBytes -gt 0)
        OutputBytes = $outBytes
        HasResultMarker = $hasResultMarker
        HasFatalError = ($fatalLines.Count -gt 0)
        FatalText = if($fatalLines.Count -gt 0){ (($fatalLines | Select-Object -First 5) -join ' | ') }else{ '' }
        WarningText = if($warningLines.Count -gt 0){ (($warningLines | Select-Object -First 5) -join ' | ') }else{ '' }
        OutLog = $outLog
        ErrLog = $errLog
    }
}
function Get-DiskMeasurementEvaluation($Detail,$Health,$DriveInfo,[ValidateSet("stability","throughput")][string]$WorkloadKind) {
    $profileDisplay = Get-DiskProfileDisplayName $DriveInfo.Profile
    $ioThr = Get-DiskRandomIopsThresholdByProfile $DriveInfo.Profile $DriveInfo.IsSystemDrive
    $title = if($WorkloadKind -eq "stability"){"4K 随机读写性能"}else{"顺序读写速度"}
    $state = "PASS"
    $actual = "-"
    $reference = "-"
    $conclusion = "通过"
    $summary = ""

    if($Health.HasFatalError){
        $state = "FAIL"
        $conclusion = "测试执行失败"
        $actual = "测试过程中检测到 I/O 或工具执行错误"
        $reference = "请查看原始日志并复核磁盘、控制器、权限和剩余空间"
        $summary = "$title：测试执行失败"
    } elseif(!$Health.HasOutput){
        $state = "FAIL"
        $conclusion = "未获得有效结果"
        $actual = "测试未生成有效结果"
        $reference = "请检查测试工具是否启动、测试文件是否创建以及磁盘剩余空间"
        $summary = "$title：未获得有效结果"
    } elseif($null -eq $Detail -or !$Detail.ParseOk){
        $state = "WARN"
        $conclusion = "结果需复核"
        $actual = "测试日志已生成，但自动汇总未能识别结果"
        $reference = "原始日志已保留，建议人工复核；该情况不等同于硬盘故障"
        $summary = "$title：结果需复核"
    } elseif($WorkloadKind -eq "stability"){
        $actual = ("<div class='result-line'><span>每秒读写次数</span><b>{0} IOPS</b></div><div class='result-line'><span>平均响应时间</span><b>{1} ms</b></div><div class='result-note'>测试条件：4KiB 数据块，70% 读取 / 30% 写入</div>" -f `
            (Format-DiskNumber $Detail.Iops 2 $true),`
            (Format-DiskNumber $Detail.AvgLatMs 3 $false))
        $reference = ("<div class='reference-main'>参考性能：≥ {0} IOPS</div><div class='result-note'>数值越高表示小文件和系统随机访问能力越强；响应时间越低越好。</div>" -f `
            (Format-DiskNumber $ioThr.PassIOPS 0 $true))
        if($null -eq $Detail.Iops -or [double]$Detail.Iops -le 0){
            $state="FAIL"; $conclusion="无有效随机读写"; $summary="$title：无有效随机读写结果"
        } elseif([double]$Detail.Iops -lt [double]$ioThr.FailIOPS){
            $state="FAIL"; $conclusion="性能严重异常"; $summary=("$title：{0} IOPS，性能严重异常" -f (Format-DiskNumber $Detail.Iops 2 $true))
        } elseif([double]$Detail.Iops -lt [double]$ioThr.PassIOPS){
            $state="WARN"; $conclusion="低于参考值"; $summary=("$title：{0} IOPS，平均响应时间 {1} ms，低于参考值" -f (Format-DiskNumber $Detail.Iops 2 $true),(Format-DiskNumber $Detail.AvgLatMs 3 $false))
        } else {
            $summary=("$title：{0} IOPS，平均响应时间 {1} ms，通过" -f (Format-DiskNumber $Detail.Iops 2 $true),(Format-DiskNumber $Detail.AvgLatMs 3 $false))
        }
    } else {
        $actual = ("<div class='result-line'><span>读取速度</span><b>{0} MiB/s</b></div><div class='result-line'><span>写入速度</span><b>{1} MiB/s</b></div><div class='result-line result-total'><span>综合读写速度</span><b>{2} MiB/s</b></div><div class='result-note'>测试条件：1MiB 数据块，70% 读取 / 30% 写入</div>" -f `
            (Format-DiskNumber $Detail.ReadMiBps 2 $false),`
            (Format-DiskNumber $Detail.WriteMiBps 2 $false),`
            (Format-DiskNumber $Detail.TotalMiBps 2 $false))
        $reference = ("<div class='reference-main'>综合读写参考：≥ {0} MiB/s</div><div class='result-note'>用于反映大文件连续读取和写入能力。</div>" -f `
            (Format-DiskNumber $DriveInfo.PassMBps 0 $true))
        if($null -eq $Detail.TotalMiBps -or [double]$Detail.TotalMiBps -le 0){
            $state="FAIL"; $conclusion="无有效顺序读写"; $summary="$title：无有效顺序读写结果"
        } elseif([double]$Detail.TotalMiBps -lt [double]$DriveInfo.FailMBps){
            $state="FAIL"; $conclusion="性能严重异常"; $summary=("$title：综合读写速度 {0} MiB/s，性能严重异常" -f (Format-DiskNumber $Detail.TotalMiBps 2 $false))
        } elseif([double]$Detail.TotalMiBps -lt [double]$DriveInfo.PassMBps){
            $state="WARN"; $conclusion="低于参考值"; $summary=("$title：读取 {0} MiB/s，写入 {1} MiB/s，综合 {2} MiB/s，低于参考值" -f (Format-DiskNumber $Detail.ReadMiBps 2 $false),(Format-DiskNumber $Detail.WriteMiBps 2 $false),(Format-DiskNumber $Detail.TotalMiBps 2 $false))
        } else {
            $summary=("$title：读取 {0} MiB/s，写入 {1} MiB/s，综合 {2} MiB/s，通过" -f (Format-DiskNumber $Detail.ReadMiBps 2 $false),(Format-DiskNumber $Detail.WriteMiBps 2 $false),(Format-DiskNumber $Detail.TotalMiBps 2 $false))
        }
    }

    if($Health.WarningText){
        $reference += "<div class='result-note'>工具日志包含提示信息，建议结合原始日志复核。</div>"
    }
    return [pscustomobject]@{
        WorkloadKind=$WorkloadKind
        Title=$title
        State=$state
        ActualHtml=$actual
        ReferenceHtml=$reference
        Conclusion=$conclusion
        Summary=$summary
        ProfileDisplay=$profileDisplay
    }
}

function Build-Report {
    $L = @{
        Title = "NVIDIA GeForce / RTX &#x6D88;&#x8D39;&#x7EA7;&#x663E;&#x5361; FurMark2 + y-cruncher &#x7A33;&#x5B9A;&#x6027;&#x6D4B;&#x8BD5;&#x62A5;&#x544A;"
        ReportDir = "&#x62A5;&#x544A;&#x76EE;&#x5F55;"
        Sec1 = "&#x4E00;&#x3001;&#x6D4B;&#x8BD5;&#x7ED3;&#x8BBA;"
        Overall = "&#x6574;&#x4F53;&#x72B6;&#x6001;"
        Conclusion = "&#x7ED3;&#x8BBA;&#x8BF4;&#x660E;"
        Pass = "&#x901A;&#x8FC7;"
        Warn = "&#x5173;&#x6CE8;"
        Fail = "&#x4E0D;&#x5408;&#x683C;"
        NotTested = "&#x672A;&#x6D4B;&#x8BD5;"
        NotDetected = "&#x672A;&#x68C0;&#x6D4B;&#x5230;"
        PassNote = "&#x672C;&#x6B21;&#x6D4B;&#x8BD5;&#x6D41;&#x7A0B;&#x5B8C;&#x6210;&#xFF0C;&#x5DF2;&#x542F;&#x7528;&#x9879;&#x76EE;&#x7684;&#x4E3B;&#x8981;&#x76D1;&#x63A7;&#x6307;&#x6807;&#x8FBE;&#x5230;&#x5F53;&#x524D;&#x901A;&#x7528;&#x5224;&#x5B9A;&#x6807;&#x51C6;&#x3002;"
        WarnNote = "&#x672C;&#x6B21;&#x6D4B;&#x8BD5;&#x6D41;&#x7A0B;&#x5B8C;&#x6210;&#xFF0C;&#x4F46;&#x90E8;&#x5206;&#x5DF2;&#x542F;&#x7528;&#x9879;&#x76EE;&#x5B58;&#x5728;&#x9700;&#x8981;&#x5173;&#x6CE8;&#x7684;&#x6307;&#x6807;&#xFF0C;&#x8BF7;&#x7ED3;&#x5408;&#x66F2;&#x7EBF;&#x548C;&#x65E5;&#x5FD7;&#x590D;&#x6838;&#x3002;"
        FailNote = "&#x672C;&#x6B21;&#x6D4B;&#x8BD5;&#x6D41;&#x7A0B;&#x5B8C;&#x6210;&#xFF0C;&#x4F46;&#x5B58;&#x5728;&#x4E0D;&#x5408;&#x683C;&#x6307;&#x6807;&#x6216;&#x5173;&#x952E;&#x9879;&#x76EE;&#x672A;&#x8FBE;&#x5230;&#x6700;&#x4F4E;&#x9608;&#x503C;&#x3002;"
        Sec2 = "&#x4E09;&#x3001;&#x6D4B;&#x8BD5;&#x4FE1;&#x606F;"
        StartTime = "&#x5F00;&#x59CB;&#x65F6;&#x95F4;"
        EndTime = "&#x7ED3;&#x675F;&#x65F6;&#x95F4;"
        Mode = "&#x6D4B;&#x8BD5;&#x6A21;&#x5F0F;"
        Interval = "&#x91C7;&#x6837;&#x95F4;&#x9694;"
        GpuStage = "GPU &#x9636;&#x6BB5;"
        CpuStage = "CPU/&#x5185;&#x5B58;&#x9636;&#x6BB5;"
        DiskStage = "&#x78C1;&#x76D8;&#x9636;&#x6BB5;"
        DiskTarget = "&#x6D4B;&#x8BD5;&#x76D8;&#x7B26;/&#x5355;&#x76D8;&#x6587;&#x4EF6;"
        MemoryTarget = "&#x5185;&#x5B58;&#x76EE;&#x6807;"
        MemoryWorkers = "&#x5185;&#x5B58;&#x5E76;&#x884C;&#x8FDB;&#x7A0B;"
        GpuBackend = "GPU &#x540E;&#x7AEF;"
        CpuBackend = "CPU/&#x5185;&#x5B58;&#x540E;&#x7AEF;"
        Seconds = "&#x79D2;"
        Minutes = "&#x5206;&#x949F;"
        Sec3 = "&#x56DB;&#x3001;&#x6D4B;&#x8BD5;&#x9636;&#x6BB5;&#x65F6;&#x95F4;"
        Phase = "&#x9636;&#x6BB5;"
        PhaseStart = "&#x5F00;&#x59CB;&#x65F6;&#x95F4;"
        PhaseEnd = "&#x7ED3;&#x675F;&#x65F6;&#x95F4;"
        Duration = "&#x6301;&#x7EED;&#x65F6;&#x95F4;"
        Sec4 = "&#x5341;&#x4E8C;&#x3001;&#x6D4B;&#x8BD5;&#x5DE5;&#x5177;&#x4FE1;&#x606F;"
        Module = "&#x6D4B;&#x8BD5;&#x6A21;&#x5757;"
        Tool = "&#x5DE5;&#x5177;"
        Backend = "&#x540E;&#x7AEF;/&#x6A21;&#x5F0F;"
        ToolPath = "&#x5DE5;&#x5177;&#x8DEF;&#x5F84;"
        KeyArgs = "&#x5173;&#x952E;&#x53C2;&#x6570;"
        Sec5 = "&#x4E8C;&#x3001;&#x786C;&#x4EF6;&#x4FE1;&#x606F;"
        SystemInfo = "&#x7CFB;&#x7EDF;&#x4FE1;&#x606F;"
        ComputerName = "Computer Name"
        OS = "OS"
        CpuVendor = "CPU Vendor"
        CPU = "CPU"
        CpuSockets = "CPU Sockets"
        CpuCores = "CPU Cores"
        CpuThreads = "CPU Threads"
        MemoryGB = "Memory GB"
        CpuModelBig = "CPU &#x578B;&#x53F7;"
        CpuSpecBig = "CPU &#x89C4;&#x683C;"
        GpuInfo = "GPU &#x4FE1;&#x606F;"
        DiskInfo = "&#x78C1;&#x76D8;&#x4FE1;&#x606F;"
        SecCriteria = "&#x4E94;&#x3001;&#x5224;&#x5B9A;&#x6807;&#x51C6;"
        Metric = "&#x6307;&#x6807;"
        PassStd = "&#x901A;&#x8FC7;&#x6807;&#x51C6;"
        WarnStd = "&#x5173;&#x6CE8;&#x6807;&#x51C6;"
        FailStd = "&#x4E0D;&#x5408;&#x683C;&#x6807;&#x51C6;"
        Remark = "&#x8BF4;&#x660E;"
        SecStatus = "&#x516D;&#x3001;&#x6D4B;&#x8BD5;&#x9879;&#x76EE;&#x72B6;&#x6001;"
        Item = "&#x6D4B;&#x8BD5;&#x9879;&#x76EE;"
        Status = "&#x72B6;&#x6001;"
        MainResult = "&#x4E3B;&#x8981;&#x7ED3;&#x679C;"
        Participate = "&#x53C2;&#x4E0E;&#x603B;&#x8BC4;"
        SecDiskResult = "&#x4E03;&#x3001;&#x78C1;&#x76D8;&#x6D4B;&#x8BD5;&#x7ED3;&#x679C;"
        SecMetrics = "&#x516B;&#x3001;&#x6838;&#x5FC3;&#x6307;&#x6807;&#x6C47;&#x603B;"
        SecStageMetrics = "&#x4E5D;&#x3001;&#x5206;&#x9879;&#x6307;&#x6807;&#x6C47;&#x603B;"
        SecCharts = "&#x5341;&#x3001;&#x8D8B;&#x52BF;&#x66F2;&#x7EBF;&#xFF08;&#x6309;&#x6D4B;&#x8BD5;&#x987A;&#x5E8F;&#xFF09;"
        ChartNote = "&#x6BCF;&#x5F20;&#x66F2;&#x7EBF;&#x6A2A;&#x8F74;&#x4E3A;&#x5B9E;&#x9645;&#x91C7;&#x6837;&#x65F6;&#x95F4;&#x3002;&#x78C1;&#x76D8;&#x66F2;&#x7EBF;&#x53EA;&#x7528;&#x4E8E;&#x89C2;&#x5BDF;&#x8D8B;&#x52BF;&#xFF0C;&#x6700;&#x7EC8;&#x5224;&#x5B9A;&#x4EE5; DiskSpd &#x7ED3;&#x679C;&#x8868;&#x4E3A;&#x51C6;&#x3002;"
        SecRaw = "&#x5341;&#x4E00;&#x3001;&#x539F;&#x59CB;&#x6570;&#x636E;&#x6587;&#x4EF6;"
        SampleCsv = "&#x91C7;&#x6837; CSV"
        GpuCsv = "GPU &#x6E29;&#x5EA6;/&#x529F;&#x8017; CSV"
        CpuSensorCsv = "CPU &#x6E29;&#x5EA6; CSV"
        MemoryLog = "&#x5185;&#x5B58;&#x538B;&#x529B;&#x65E5;&#x5FD7;"
        EventLog = "&#x4E8B;&#x4EF6;&#x65E5;&#x5FD7;"
        Description = "&#x8BF4;&#x660E;"
        Scope = "&#x9002;&#x7528;&#x8303;&#x56F4;"
        FooterDesc = "&#x672C;&#x62A5;&#x544A;&#x7528;&#x4E8E;&#x670D;&#x52A1;&#x5668;/&#x5DE5;&#x4F5C;&#x7AD9;&#x4EA4;&#x4ED8;&#x524D;&#x7A33;&#x5B9A;&#x6027;&#x9A8C;&#x8BC1;&#xFF0C;&#x7ED3;&#x8BBA;&#x57FA;&#x4E8E;&#x672C;&#x6B21;&#x6D4B;&#x8BD5;&#x671F;&#x95F4;&#x91C7;&#x96C6;&#x5230;&#x7684; CPU&#x3001;&#x5185;&#x5B58;&#x3001;GPU&#x3001;&#x78C1;&#x76D8;&#x6307;&#x6807;&#x3002;"
        FooterScope = "GPU &#x6A21;&#x5757;&#x9762;&#x5411; NVIDIA GeForce / RTX &#x6D88;&#x8D39;&#x7EA7;&#x56FE;&#x5F62;&#x5361;&#xFF0C;&#x9ED8;&#x8BA4;&#x91C7;&#x7528; FurMark &#x56FE;&#x5F62;&#x8D1F;&#x8F7D;&#xFF1B;CPU/&#x5185;&#x5B58;&#x9ED8;&#x8BA4;&#x91C7;&#x7528; y-cruncher&#xFF0C;AMD &#x5E73;&#x53F0;&#x53EF;&#x81EA;&#x52A8; fallback &#x5230;&#x5185;&#x7F6E; CPU burner + memory workers&#x3002;"
        CpuPressure = "CPU &#x538B;&#x529B;"
        MemPressure = "&#x5185;&#x5B58;&#x538B;&#x529B;"
        GpuPressure = "GPU &#x56FE;&#x5F62;&#x538B;&#x529B;"
        DiskPressure = "&#x78C1;&#x76D8; I/O"
        Yes = "&#x662F;"
        No = "&#x5426;"
        CpuMax = "CPU &#x6700;&#x5927;&#x4F7F;&#x7528;&#x7387;"
        CpuAvg = "CPU &#x5E73;&#x5747;&#x4F7F;&#x7528;&#x7387;"
        CpuClockMax = "CPU &#x6700;&#x5927;&#x5F53;&#x524D;&#x9891;&#x7387;"
        CpuClockAvg = "CPU &#x5E73;&#x5747;&#x5F53;&#x524D;&#x9891;&#x7387;"
        CpuTempMax = "CPU &#x6700;&#x9AD8;&#x6E29;&#x5EA6;"
        CpuTempAvg = "CPU &#x5E73;&#x5747;&#x6E29;&#x5EA6;"
        CpuPowerMax = "CPU &#x6700;&#x5927;&#x529F;&#x8017;"
        CpuPowerAvg = "CPU &#x5E73;&#x5747;&#x529F;&#x8017;"
        MemMax = "&#x5185;&#x5B58;&#x6700;&#x5927;&#x4F7F;&#x7528;&#x7387;"
        MemAvg = "&#x5185;&#x5B58;&#x5E73;&#x5747;&#x4F7F;&#x7528;&#x7387;"
        GpuUtilMax = "GPU &#x6700;&#x5927;&#x4F7F;&#x7528;&#x7387;"
        GpuTempMax = "GPU &#x6700;&#x9AD8;&#x6E29;&#x5EA6;"
        GpuPowerMax = "GPU &#x6700;&#x5927;&#x603B;&#x529F;&#x8017;"
        GpuMemMax = "GPU &#x6700;&#x5927;&#x663E;&#x5B58;&#x5360;&#x7528;"
        DiskReadMax = "&#x78C1;&#x76D8;&#x6700;&#x5927;&#x8BFB;&#x53D6;"
        DiskWriteMax = "&#x78C1;&#x76D8;&#x6700;&#x5927;&#x5199;&#x5165;"
        GpuUtilChart = "GPU &#x4F7F;&#x7528;&#x7387;"
        GpuTempChart = "GPU &#x6E29;&#x5EA6;"
        GpuPowerChart = "GPU &#x529F;&#x8017;"
        GpuMemChart = "GPU &#x663E;&#x5B58;&#x5360;&#x7528;"
        CpuUtilChart = "CPU &#x4F7F;&#x7528;&#x7387;"
        CpuClockChart = "CPU &#x5F53;&#x524D;&#x9891;&#x7387;"
        CpuTempChart = "CPU &#x6E29;&#x5EA6;"
        CpuPowerChart = "CPU &#x529F;&#x8017;"
        MemChart = "&#x5185;&#x5B58;&#x4F7F;&#x7528;&#x7387;"
        DiskReadChart = "&#x78C1;&#x76D8;&#x8BFB;&#x53D6;&#x901F;&#x5EA6;"
        DiskWriteChart = "&#x78C1;&#x76D8;&#x5199;&#x5165;&#x901F;&#x5EA6;"
        NoGpuText = "&#x672A;&#x68C0;&#x6D4B;&#x5230; NVIDIA GPU"
        GpuNotTestedText = "GPU &#x9636;&#x6BB5;&#x672A;&#x542F;&#x7528;&#xFF0C;&#x72B6;&#x6001;&#x4E3A;&#x672A;&#x6D4B;&#x8BD5;&#xFF0C;&#x4E0D;&#x53C2;&#x4E0E;&#x603B;&#x4F53;&#x7ED3;&#x8BBA;&#x3002;"
        AllFixedDrives = "&#x6240;&#x6709;&#x672C;&#x5730;&#x56FA;&#x5B9A;&#x76D8;&#xFF08;&#x5305;&#x62EC; C:&#xFF09;"
        DiskLowSpace = "&#x78C1;&#x76D8;&#x7A7A;&#x95F4;&#x4E0D;&#x8DB3;&#x6216;&#x65E0;&#x53EF;&#x7528;&#x56FA;&#x5B9A;&#x76D8;&#x65F6;&#xFF0C;&#x78C1;&#x76D8;&#x9636;&#x6BB5;&#x8DF3;&#x8FC7;&#xFF0C;&#x4E0D;&#x8BEF;&#x62A5;&#x5176;&#x4ED6;&#x9879;&#x76EE;&#x5F02;&#x5E38;&#x3002;"
    }
    $EndTime=Get-Date
    $rows=@(); if(Test-Path $MonitorCsv){ $rows=@(Import-Csv $MonitorCsv) }
    $gpuRows=@($rows|Where-Object {$_.Phase -eq "gpu" -or $_.Phase -eq "all"})
    $cpuRows=@($rows|Where-Object {$_.Phase -eq "cpu" -or $_.Phase -eq "all"})
    $diskRows=@($rows|Where-Object {$_.Phase -eq "disk" -or $_.Phase -eq "disk-throughput-probe" -or $_.Phase -eq "all"})
    $diskStabilityRows=@($rows|Where-Object {$_.Phase -eq "disk"})
    $diskThroughputRows=@($rows|Where-Object {$_.Phase -eq "disk-throughput-probe"})
    $cpuJudgeRows=@(Get-StableRows $cpuRows $CpuStableSkipStartSeconds $CpuStableSkipEndSeconds)
    $gpuJudgeRows=@(Get-GpuEffectiveRows $gpuRows)
    $cpuMax=Get-Max $cpuRows "CPU_Percent"; $cpuAvg=Get-Avg $cpuJudgeRows "CPU_Percent"
    $cpuTemp=Get-Max $cpuRows "CPU_Temperature_C"; $cpuTempAvg=Get-Avg $cpuRows "CPU_Temperature_C"
    $cpuPower=Get-Max $cpuRows "CPU_Package_Power_W"; $cpuPowerAvg=Get-Avg $cpuJudgeRows "CPU_Package_Power_W"
    $cpuPowerAvailable = ($null -ne $cpuPower -and [double]$cpuPower -gt 0)
    $cpuPowerAvgAvailable = ($null -ne $cpuPowerAvg -and [double]$cpuPowerAvg -gt 0)
    if(!$cpuPowerAvailable){ $cpuPower=$null; $cpuPowerAvg=$null }
    $cpuPowerLimitW=Get-CpuPowerLimitFromRows $cpuJudgeRows
    $cpuPowerLimitAvailable = ($null -ne $cpuPowerLimitW -and [double]$cpuPowerLimitW -gt 0)
    $cpuOfficialTdpW=$script:CpuOfficialTdpW
    $cpuPowerBaselineW = if($cpuPowerLimitAvailable){$cpuPowerLimitW}else{$cpuOfficialTdpW}
    $cpuPowerBaselineAvailable = ($null -ne $cpuPowerBaselineW -and [double]$cpuPowerBaselineW -gt 0)
    $cpuClock=Get-Max $cpuRows "CPU_Clock_Current_MHz"; $cpuClockAvg=Get-Avg $cpuRows "CPU_Clock_Current_MHz"
    $memMax=Get-Max $cpuRows "Memory_Used_Percent"; $memAvg=Get-Avg $cpuRows "Memory_Used_Percent"
    $gpuUtil=Get-Max $gpuRows "GPU_Util_Max_Percent"
    $gpuUtilAvg=Get-Avg $gpuJudgeRows "GPU_Util_Max_Percent"
    $gpuTemp=Get-Max $gpuRows "GPU_Temp_Max_C"
    $gpuTempAvg=Get-Avg $gpuJudgeRows "GPU_Temp_Max_C"
    $gpuFan=Get-Max $gpuRows "GPU_Fan_Max_Percent"
    $gpuFanAvg=Get-Avg $gpuJudgeRows "GPU_Fan_Max_Percent"
    $gpuPower=Get-Max $gpuRows "GPU_Power_Total_W"
    $gpuPowerAvg=Get-Avg $gpuJudgeRows "GPU_Power_Total_W"
    $gpuPowerLimitW=$script:GpuPowerLimitW
    $gpuThermalSlowdownC=$script:GpuThermalSlowdownC
    $gpuPowerLimitAvailable = ($null -ne $gpuPowerLimitW -and [double]$gpuPowerLimitW -gt 0)
    $gpuThermalLimitAvailable = ($null -ne $gpuThermalSlowdownC -and [double]$gpuThermalSlowdownC -gt 0)
    # Legacy/low-end GPUs (for example GT 730) may not expose utilization/power telemetry.
    # Use explicit availability flags so missing data can never be judged as FAIL/ACCEPTABLE.
    $gpuUtilAvailable = ($null -ne $gpuUtil)
    $gpuUtilAvgAvailable = ($null -ne $gpuUtilAvg)
    $gpuPowerAvailable = ($null -ne $gpuPower -and [double]$gpuPower -gt 0)
    $gpuPowerAvgAvailable = ($null -ne $gpuPowerAvg -and [double]$gpuPowerAvg -gt 0)
    if(!$gpuPowerAvailable){ $gpuPower = $null }
    $gpuMem=Get-Max $gpuRows "GPU_Mem_Used_Total_MB"
    $gpuCnt=Get-Max $rows "GPU_Count"
    $diskRead=Get-Max $diskRows "Disk_Read_MBps"; $diskWrite=Get-Max $diskRows "Disk_Write_MBps"
    $diskTotal=0; if($null -ne $diskRead){$diskTotal+=$diskRead}; if($null -ne $diskWrite){$diskTotal+=$diskWrite}
    $diskSpd=Get-DiskSpdParsedResult
    $diskJudgeTotal=$diskTotal; $diskJudgeRead=$diskRead; $diskJudgeWrite=$diskWrite; $diskJudgeSource="real-time monitor"
    if($diskSpd.TotalMiBps -ne $null){ $diskJudgeTotal=$diskSpd.TotalMiBps; $diskJudgeRead=$diskSpd.ReadMiBps; $diskJudgeWrite=$diskSpd.WriteMiBps; $diskJudgeSource="DiskSpd 最终结果" }
    $gpuDetected = ($gpuCnt -ne $null -and $gpuCnt -gt 0)
    $gpuEnabled = (($Mode -eq "staged" -and $GpuMinutes -gt 0) -or (($Mode -eq "gpu" -or $Mode -eq "all") -and $DurationHours -gt 0) -or $AllHours -gt 0)
    $cpuEnabled = (($Mode -eq "staged" -and $CpuMinutes -gt 0) -or (($Mode -eq "cpu" -or $Mode -eq "all") -and $DurationHours -gt 0) -or $AllHours -gt 0)
    $diskEnabled = (($Mode -eq "staged" -and $DiskMinutes -gt 0) -or (($Mode -eq "disk" -or $Mode -eq "all") -and ($DurationHours -gt 0 -or $DiskMinutes -gt 0)) -or $AllHours -gt 0) -and !$script:SkipDiskPhase
    if($script:SupplementMergeMode){
        if($gpuRows.Count -gt 0){ $gpuEnabled = $true }
        if($cpuRows.Count -gt 0){ $cpuEnabled = $true }
        if($diskRows.Count -gt 0){ $diskEnabled = $true }
    }
    $script:StatusItems = @()
    if($gpuEnabled -and !$gpuDetected){ Add-Status $L.GpuPressure "NOT_TESTED" "未检测到 NVIDIA GPU，GPU 压测未执行" $false }
    elseif(!$gpuEnabled){ Add-Status $L.GpuPressure "NOT_TESTED" $L.GpuNotTestedText $false }
    elseif($gpuTemp -ne $null -and $gpuTemp -ge $GpuTempFailC){ Add-Status $L.GpuPressure "FAIL" ("GPU temp {0} C >= {1} C; critical thermal limit exceeded" -f $gpuTemp,$GpuTempFailC) $true }
    elseif($gpuThermalLimitAvailable -and $gpuTempAvg -ne $null -and $gpuTempAvg -ge $gpuThermalSlowdownC){ Add-Status $L.GpuPressure "FAIL" ("GPU average hottest temperature {0} C >= driver slowdown limit {1} C" -f $gpuTempAvg,$gpuThermalSlowdownC) $true }
    elseif($gpuUtil -ne $null -and $gpuUtil -lt 80){ Add-Status $L.GpuPressure "FAIL" ("GPU max utilization {0}% < 80%; GPU stress load did not start correctly" -f $gpuUtil) $true }
    elseif($gpuPowerLimitAvailable -and $gpuPowerAvg -ne $null -and $gpuPowerAvg -lt ($gpuPowerLimitW * 0.50)){ Add-Status $L.GpuPressure "FAIL" ("GPU average total power {0} W < 50% of driver power limit {1} W" -f $gpuPowerAvg,$gpuPowerLimitW) $true }
    else{
        $extra=""
        if($gpuUtilAvg -ne $null -and $gpuUtilAvg -lt $GpuAvgLoadPassPercent){ $extra="; effective avg below reference because startup/stop samples or load window may be short" }
        if($gpuPowerLimitAvailable -and $gpuPowerAvg -ne $null -and $gpuPowerAvg -lt ($gpuPowerLimitW * 0.70)){ $extra += "; average power below 70% of driver power limit" }
        Add-Status $L.GpuPressure "PASS" ("Max util: {0}%; Effective avg: {1}%; Max temp: {2} C; Max fan: {3}%; Max power: {4} W{5}" -f $gpuUtil,$gpuUtilAvg,$gpuTemp,$gpuFan,$gpuPower,$extra) $true
    }
    if($gpuDetected -and $gpuEnabled){
        if($gpuFan -eq $null -or $gpuFan -lt 0){ Add-Status "Cooling / Fan" "NOT_DETECTED" "GPU fan.speed is N/A or unsupported by this GPU/driver; reference only" $false }
        elseif($gpuTemp -ne $null -and $gpuTemp -ge $GpuTempFailC -and $gpuFan -lt 60){ Add-Status "Cooling / Fan" "FAIL" ("GPU temp {0} C but fan speed only {1}%; possible cooling control problem" -f $gpuTemp,$gpuFan) $true }
        else{ Add-Status "Cooling / Fan" "PASS" ("GPU fan max: {0}%; effective avg: {1}%; fan telemetry is reference only" -f $gpuFan,$gpuFanAvg) $false }
    }
    if(!$cpuEnabled){ Add-Status $L.CpuPressure "NOT_TESTED" "CPU stage disabled" $false }
    elseif($cpuTemp -ne $null -and $cpuTemp -ge $CpuTempFailC){ Add-Status $L.CpuPressure "FAIL" ("CPU temp {0} C >= {1} C; critical thermal limit exceeded" -f $cpuTemp,$CpuTempFailC) $true }
    elseif($cpuMax -ne $null -and $cpuMax -lt 80){ Add-Status $L.CpuPressure "FAIL" ("CPU max utilization {0}% < 80%; CPU stress load did not start correctly" -f $cpuMax) $true }
    elseif($cpuAvg -ne $null -and $cpuAvg -lt 50){ Add-Status $L.CpuPressure "FAIL" ("Stable-window CPU avg utilization {0}% < 50%; CPU stress load was insufficient" -f $cpuAvg) $true }
    else{
        $tempText=if($cpuTemp -eq $null){"not collected"}else{"$cpuTemp C"}
        $powerText=if($cpuPower -eq $null){"not collected"}else{"$cpuPower W"}
        $extra=""
        if($cpuTemp -eq $null){ $extra="; temperature sensor unavailable, not treated as hardware failure" }
        elseif($cpuTemp -ge $CpuTempWarnC){ $extra="; temperature is above reference but below critical limit" }
        if($cpuAvg -ne $null -and $cpuAvg -lt $CpuAvgLoadPassPercent){ $extra += "; stable avg below strict reference, accepted for short staged test" }
        Add-Status $L.CpuPressure "PASS" ("Max util: {0}%; Stable avg: {1}%; Max temp: {2}; Max package power: {3}{4}" -f $cpuMax,$cpuAvg,$tempText,$powerText,$extra) $true
    }
    if($cpuEnabled){
        $memTargetPass=[math]::Round($MemoryStressPercent*$MemoryLoadPassPercentOfTarget/100.0,1)
        $memTargetFail=[math]::Round($MemoryStressPercent*50/100.0,1)
        if($MemoryStressPercent -gt 0 -and $memMax -ne $null -and $memMax -lt $memTargetFail){ Add-Status $L.MemPressure "FAIL" ("Memory max usage {0}% is far below target reference {1}%; memory workers may not have run" -f $memMax,$memTargetFail) $true }
        else{
            $backendText = if($script:CpuMemBackendUsed){$script:CpuMemBackendUsed}else{"Unknown"}
            $policyText = if($script:CpuMemBackendUsed -eq "Fallback CPU+Memory Worker"){
                "Fallback memory workers target ${YCruncherMemoryPercent}% RAM (workers=${MemoryStressWorkers}, reserve=${MemoryReserveGB}GB)"
            } else {
                "y-cruncher controls memory target (${YCruncherMemoryPercent}% RAM)"
            }
            $reasonText = if($script:CpuMemBackendReason){"; Reason: $script:CpuMemBackendReason"}else{""}
            Add-Status $L.MemPressure "PASS" ("Max usage: {0}%; Avg usage: {1}%; Backend: {2}; Memory policy: {3}{4}; test completes without OOM/hang/reboot is PASS" -f $memMax,$memAvg,$backendText,$policyText,$reasonText) $true
        }
    } else { Add-Status $L.MemPressure "NOT_TESTED" "CPU/memory stage disabled" $false }
    $diskOverallPass = $true
    $diskModuleState = "PASS"
    $diskStatusLines = @()
    $diskMetricItems = @()
    $diskStageSummaryItems = @()
    $diskResultTableRows = ""
    if(!$diskEnabled){
        Add-Status $L.DiskPressure "NOT_TESTED" $L.DiskLowSpace $false
        $diskResultTableHtml = "<div class='disk-guide'>磁盘阶段未启用或没有满足空间条件的测试盘。</div>"
    } else {
        $stabilityMap=@{}
        $throughputMap=@{}
        foreach($dd in @($diskSpd.Details)){
            if($dd -and $dd.Drive){
                $key=(Normalize-DriveLetter $dd.Drive)
                if($dd.WorkloadKind -eq "throughput"){ $throughputMap[$key] = $dd }
                else { $stabilityMap[$key] = $dd }
            }
        }

        $expectedKinds = @()
        if($DiskIoProfile -eq "stability"){ $expectedKinds=@("stability") }
        elseif($DiskIoProfile -eq "throughput"){ $expectedKinds=@("throughput") }
        else { $expectedKinds=@("stability","throughput") }

        foreach($d0 in $script:ResolvedTestDrives){
            $d = Normalize-DriveLetter $d0
            $di = Get-DiskDriveThresholdInfo $d
            $role = Get-DiskRoleDisplayName $di.IsSystemDrive
            $profileDisplay = Get-DiskProfileDisplayName $di.Profile
            $modelText = if([string]::IsNullOrWhiteSpace("$($di.Model)")){"型号未透传"}else{"$($di.Model)"}
            $driveState = "PASS"
            $driveSummaries = @()

            foreach($kind in $expectedKinds){
                $map = if($kind -eq "throughput"){$throughputMap}else{$stabilityMap}
                $detail = $null
                if($map.ContainsKey($d)){ $detail = $map[$d] }
                $health = Get-DiskSpdLogHealth $d $kind
                $eval = Get-DiskMeasurementEvaluation $detail $health $di $kind

                if($eval.State -eq "FAIL"){
                    $driveState = "FAIL"
                    $diskModuleState = "FAIL"
                    $diskOverallPass = $false
                } elseif($eval.State -eq "WARN" -and $driveState -ne "FAIL"){
                    $driveState = "WARN"
                    if($diskModuleState -eq "PASS"){ $diskModuleState = "WARN" }
                }

                $driveSummaries += $eval.Summary
                $judgeHtml = if($eval.State -eq "PASS"){
                    "<span class='pass'>通过</span>"
                } elseif($eval.State -eq "WARN"){
                    "<span class='warn'>关注</span>"
                } else {
                    "<span class='fail'>不合格</span>"
                }
                $judgeNote = if($eval.State -eq "PASS"){""}else{"<br><span class='muted'>$(Html $eval.Conclusion)</span>"}
                $diskResultTableRows += ("<tr><td><b>{0}</b><br><span class='muted'>{1}</span></td><td><b>{2}</b><br><span class='muted'>{3}</span></td><td><b>{4}</b></td><td>{5}</td><td>{6}</td><td class='disk-judge'>{7}{8}</td></tr>" -f `
                    (Html $d),(Html $role),(Html $profileDisplay),(Html $modelText),(Html $eval.Title),$eval.ActualHtml,$eval.ReferenceHtml,$judgeHtml,$judgeNote)

                $metricResult = if($kind -eq "stability" -and $null -ne $detail -and $detail.ParseOk){
                    ("每秒读写次数：{0} IOPS | 平均响应时间：{1} ms" -f `
                        (Format-DiskNumber $detail.Iops 2 $true),(Format-DiskNumber $detail.AvgLatMs 3 $false))
                } elseif($kind -eq "throughput" -and $null -ne $detail -and $detail.ParseOk){
                    ("读取速度：{0} MiB/s | 写入速度：{1} MiB/s | 综合读写速度：{2} MiB/s" -f `
                        (Format-DiskNumber $detail.ReadMiBps 2 $false),(Format-DiskNumber $detail.WriteMiBps 2 $false),(Format-DiskNumber $detail.TotalMiBps 2 $false))
                } else {
                    $eval.Summary
                }
                $diskMetricItems += [pscustomobject]@{
                    Name=("磁盘 {0} - {1}" -f $d,$eval.Title)
                    Result=$metricResult
                    State=$eval.State
                }
                $diskStageSummaryItems += [pscustomobject]@{
                    Label=("{0} {1}" -f $d,$eval.Title)
                    Value=$metricResult
                    State=$eval.State
                }
            }

            $driveConclusion = if($driveState -eq "PASS"){"通过"}elseif($driveState -eq "WARN"){"关注"}else{"不合格"}
            $diskStatusLines += ("{0}：{1}，{2}，{3}" -f $d,$role,$profileDisplay,$modelText)
            foreach($driveSummary in $driveSummaries){
                $diskStatusLines += ("{0}：{1}" -f $d,$driveSummary)
            }
            $diskStatusLines += ("{0}：综合结论 {1}" -f $d,$driveConclusion)
        }

        if($script:ResolvedTestDrives.Count -eq 0){
            $diskModuleState = "FAIL"
            $diskOverallPass = $false
            $diskStatusLines += "没有解析到可测试的本地固定盘"
        }

        if($diskModuleState -eq "FAIL"){
            Add-Status $L.DiskPressure "FAIL" ($diskStatusLines -join "; ") $true
        } elseif($diskModuleState -eq "WARN"){
            Add-Status $L.DiskPressure "WARN" ($diskStatusLines -join "; ") $true
        } else {
            Add-Status $L.DiskPressure "PASS" ($diskStatusLines -join "; ") $true
        }

        if([string]::IsNullOrWhiteSpace($diskResultTableRows)){
            $diskResultTableRows = "<tr><td colspan='6'>没有可显示的磁盘结果。请查看 logs 目录中的 DiskSpd 原始日志。</td></tr>"
        }
        $diskResultTableHtml = @"
<div class='disk-guide'>
  <b>测试说明：</b>4K 随机读写用于反映系统盘、小文件和程序启动时的响应能力；顺序读写用于反映大文件连续传输能力。本次两项测试均采用 70% 读取、30% 写入的混合负载。
</div>
<table class='disk-result-table'>
<tr><th style='width:9%'>盘符</th><th style='width:21%'>磁盘类型与型号</th><th style='width:16%'>测试内容</th><th style='width:25%'>实测结果</th><th style='width:18%'>参考标准</th><th style='width:11%'>结果</th></tr>
$diskResultTableRows
</table>
"@
    }
    $overall="PASS"
    foreach($s in $script:StatusItems|Where-Object {$_.Participate}){
        if($s.Status -eq "FAIL"){
            $overall="FAIL"
            break
        }
        if($s.Status -eq "WARN" -and $overall -eq "PASS"){ $overall="WARN" }
    }
    $note=$L.PassNote; if($overall -eq "WARN"){$note=$L.WarnNote} elseif($overall -eq "FAIL"){$note=$L.FailNote}
    New-SvgChart (Join-Path $ChartDir "gpu_util.svg") $gpuRows "GPU_Util_Max_Percent" "GPU Max Utilization" " %"
    New-SvgChart (Join-Path $ChartDir "gpu_temp.svg") $gpuRows "GPU_Temp_Max_C" "GPU Max Temperature" " C"
    New-SvgChart (Join-Path $ChartDir "gpu_fan.svg") $gpuRows "GPU_Fan_Max_Percent" "GPU Fan Speed" " %"
    New-SvgChart (Join-Path $ChartDir "gpu_power.svg") $gpuRows "GPU_Power_Total_W" "GPU Total Power" " W"
    New-SvgChart (Join-Path $ChartDir "gpu_memory.svg") $gpuRows "GPU_Mem_Used_Total_MB" "GPU Total Memory Used" " MB"
    New-SvgChart (Join-Path $ChartDir "cpu_percent.svg") $cpuRows "CPU_Percent" "CPU Utilization" " %"
    New-SvgChart (Join-Path $ChartDir "cpu_clock.svg") $cpuRows "CPU_Clock_Current_MHz" "CPU Current Clock" " MHz"
    New-SvgChart (Join-Path $ChartDir "cpu_temp.svg") $cpuRows "CPU_Temperature_C" "CPU Temperature" " C"
    New-SvgChart (Join-Path $ChartDir "cpu_power.svg") $cpuRows "CPU_Package_Power_W" "CPU Package Power" " W"
    New-SvgChart (Join-Path $ChartDir "memory_percent.svg") $cpuRows "Memory_Used_Percent" "Memory Used" " %"
    New-SvgChart (Join-Path $ChartDir "disk_read.svg") $diskRows "Disk_Read_MBps" "Disk Read Throughput" " MB/s"
    New-SvgChart (Join-Path $ChartDir "disk_write.svg") $diskRows "Disk_Write_MBps" "Disk Write Throughput" " MB/s"
    $diskTargets = if($script:ResolvedTestDrives.Count -gt 0){ ($script:ResolvedTestDrives -join ', ') + ' / ' + $DiskFileSize } else { '-' }
    $gpuNotDetected = ($script:GpuTestStatus -eq "Not Tested" -and $script:GpuTestReason -match "NVIDIA GPU|未检测到")
    $gpuStatusDisplay = if($gpuNotDetected){"未测试（未检测到 NVIDIA GPU）"} elseif([string]::IsNullOrWhiteSpace($script:GpuTestStatus)){"-"} else {$script:GpuTestStatus}
    $gpuPlanDisplay = if($gpuNotDetected){"未测试"} else {"$GpuMinutes 分钟"}
    $gpuActualDisplay = if($gpuNotDetected){"0 秒"} elseif($script:GpuActualSeconds -gt 0){"$($script:GpuActualSeconds) 秒"} else {"-"}
    $gpuReasonDisplay = if($gpuNotDetected){"未检测到 NVIDIA GPU"} elseif([string]::IsNullOrWhiteSpace($script:GpuTestReason)){"-"} else {$script:GpuTestReason}
    $gpuBackendDisplay = if($gpuNotDetected){"未测试"} else {$GpuBackend}
    $gpuToolDisplay = if($gpuNotDetected){"未测试"} else {"FurMark 2 / Auto GPU stress"}
    $testInfo=""
    $testInfo += "<tr><th>$($L.StartTime)</th><td>$(Html $StartTime)</td><th>$($L.EndTime)</th><td>$(Html $EndTime)</td></tr>"
    $testInfo += "<tr><th>$($L.Mode)</th><td>$(Html $Mode)</td><th>$($L.Interval)</th><td>$IntervalSeconds $($L.Seconds)</td></tr>"
    $testInfo += "<tr><th>$($L.GpuStage)</th><td>$(Html $gpuPlanDisplay)</td><th>$($L.CpuStage)</th><td>$CpuMinutes $($L.Minutes)</td></tr>"
    $diskStageDisplay = "$DiskMinutes $($L.Minutes)"
    if($DiskIoProfile -eq "both" -and $DiskBothTimePolicy -eq "split"){
        $totalSecForInfo=[int][math]::Round($DiskMinutes*60)
        $planForInfo=Get-DiskBothSplitDurations $totalSecForInfo
        $stabMin=[math]::Round($planForInfo.StabilitySeconds/60,1)
        $thrMin=[math]::Round($planForInfo.ThroughputSeconds/60,1)
        $diskStageDisplay = "$DiskMinutes $($L.Minutes)（稳定性 $stabMin $($L.Minutes) + 速度 $thrMin $($L.Minutes)）"
    } elseif($DiskIoProfile -eq "both") {
        $diskStageDisplay = "$DiskMinutes $($L.Minutes) + 速度探针 $DiskThroughputProbeSeconds 秒"
    }
    $testInfo += "<tr><th>$($L.DiskStage)</th><td>$diskStageDisplay</td><th>$($L.DiskTarget)</th><td>$(Html $diskTargets)</td></tr>"
    $testInfo += "<tr><th>$($L.MemoryTarget)</th><td>y-cruncher policy $YCruncherMemoryPercent% RAM</td></tr>"
    $testInfo += "<tr><th>$($L.GpuBackend)</th><td>$(Html $gpuBackendDisplay)</td><th>$($L.CpuBackend)</th><td>$(Html $CpuMemBackend)</td></tr>"
    $testInfo += "<tr><th>GPU 状态</th><td>$(Html $gpuStatusDisplay)</td><th>GPU 实际时长</th><td>$(Html $gpuActualDisplay)</td></tr>"
    $diskProbeText = if($DiskIoProfile -eq "both" -and $DiskBothTimePolicy -eq "split"){ "已包含在磁盘总时长内" } elseif($DiskIoProfile -eq "both") { "$DiskThroughputProbeSeconds 秒（在总时长外追加）" } elseif($DiskIoProfile -eq "throughput") { "仅进行顺序读写测试" } else { "未启用" }
    $diskPolicyText = if($DiskIoProfile -eq "both"){
        if($DiskBothTimePolicy -eq "split" -or [string]::IsNullOrWhiteSpace($DiskBothTimePolicy)){ "随机读写与顺序读写平均分配总时长" }
        else { "顺序读写测试在稳定性测试后追加" }
    } else { "单项测试" }
    $diskProfileDisplay = if($DiskIoProfile -eq "both"){"随机读写 + 顺序读写"}elseif($DiskIoProfile -eq "stability"){"随机读写"}else{"顺序读写"}
    # v95/v96: report actual execution state, not merely whether Mode selected the module.
    $gpuTestEnabled = $gpuEnabled
    $cpuTestEnabled = $cpuEnabled
    $diskTestEnabled = $diskEnabled

    $gpuModuleStatus = if(!$gpuTestEnabled){
        "未测试（未启用）"
    } elseif($script:GpuTestStatus -eq "PASS"){
        "已测试"
    } elseif($script:GpuTestStatus -eq "Running"){
        "未测试（测试未正常结束）"
    } elseif($gpuNotDetected){
        "未测试（未检测到 NVIDIA GPU）"
    } else {
        $reason = if([string]::IsNullOrWhiteSpace($script:GpuTestReason)){"GPU 压力程序未成功启动"}else{$script:GpuTestReason}
        "未测试（$reason）"
    }

    $cpuModuleStatus = if(!$cpuTestEnabled){
        "未测试（未启用）"
    } elseif($script:CpuModuleExecuted){
        "已测试"
    } else {
        $reason = if([string]::IsNullOrWhiteSpace($script:CpuModuleReason)){"CPU/内存压力程序未成功启动"}else{$script:CpuModuleReason}
        "未测试（$reason）"
    }

    $diskModuleStatus = if(!$diskTestEnabled){
        $reason = if($script:SkipDiskPhase -and ![string]::IsNullOrWhiteSpace($script:DiskModuleReason)){$script:DiskModuleReason}else{"未启用"}
        "未测试（$reason）"
    } elseif($script:DiskModuleExecuted){
        "已测试"
    } else {
        $reason = if([string]::IsNullOrWhiteSpace($script:DiskModuleReason)){"DiskSpd 未成功启动或没有有效测试结果"}else{$script:DiskModuleReason}
        "未测试（$reason）"
    }

    $cpuBackendDisplay = if($script:CpuModuleExecuted){
        if($script:CpuMemBackendUsed -and $script:CpuMemBackendUsed -notin @("NotStarted","Unknown")){$script:CpuMemBackendUsed}else{$CpuMemBackend}
    } else { "未测试" }
    $cpuModuleReasonDisplay = if($script:CpuModuleExecuted){
        if([string]::IsNullOrWhiteSpace($script:CpuMemBackendReason)){"-"}else{$script:CpuMemBackendReason}
    } else {
        if([string]::IsNullOrWhiteSpace($script:CpuModuleReason)){"未执行 CPU/内存压力测试"}else{$script:CpuModuleReason}
    }
    $diskModuleReasonDisplay = if($script:DiskModuleExecuted){"-"}else{
        if([string]::IsNullOrWhiteSpace($script:DiskModuleReason)){"未执行磁盘压力测试"}else{$script:DiskModuleReason}
    }

    $testInfoCards = @"
<div class='info-grid'>
  <div class='info-card span-2'>
    <div class='card-title'>总体测试信息</div>
    <div class='info-row'><div class='info-key'>$($L.StartTime)</div><div class='info-val'>$(Html $StartTime)</div></div>
    <div class='info-row'><div class='info-key'>$($L.EndTime)</div><div class='info-val'>$(Html $EndTime)</div></div>
    <div class='info-row'><div class='info-key'>$($L.Mode)</div><div class='info-val'>$(Html $Mode)</div></div>
    <div class='info-row'><div class='info-key'>$($L.Interval)</div><div class='info-val'>$IntervalSeconds $($L.Seconds)</div></div>
  </div>
  <div class='info-card'>
    <div class='card-title'>GPU 测试模块</div>
    <div class='info-row'><div class='info-key'>执行状态</div><div class='info-val'>$(Html $gpuModuleStatus)</div></div>
    $(if($gpuTestEnabled){
@"
    <div class='info-row'><div class='info-key'>阶段时长</div><div class='info-val'>$(Html $gpuPlanDisplay)</div></div>
    <div class='info-row'><div class='info-key'>实际时长</div><div class='info-val'>$(Html $gpuActualDisplay)</div></div>
    <div class='info-row'><div class='info-key'>后端</div><div class='info-val'>$(Html $gpuBackendDisplay)</div></div>
    <div class='info-row'><div class='info-key'>说明</div><div class='info-val'>$(Html $gpuReasonDisplay)</div></div>
    <div class='info-row'><div class='info-key'>工具</div><div class='info-val'>$(Html $gpuToolDisplay)</div></div>
"@
    })
  </div>
  <div class='info-card'>
    <div class='card-title'>CPU / 内存测试模块</div>
    <div class='info-row'><div class='info-key'>执行状态</div><div class='info-val'>$(Html $cpuModuleStatus)</div></div>
    $(if($cpuTestEnabled -or $script:CpuModuleAttempted){
@"
    <div class='info-row'><div class='info-key'>阶段时长</div><div class='info-val'>$CpuMinutes $($L.Minutes)</div></div>
    <div class='info-row'><div class='info-key'>实际后端</div><div class='info-val'>$(Html $cpuBackendDisplay)</div></div>
    <div class='info-row'><div class='info-key'>$($L.MemoryTarget)</div><div class='info-val'>y-cruncher policy $YCruncherMemoryPercent% RAM</div></div>
    <div class='info-row'><div class='info-key'>说明</div><div class='info-val'>$(Html $cpuModuleReasonDisplay)</div></div>
"@
    })
  </div>
  <div class='info-card span-2'>
    <div class='card-title'>磁盘测试模块</div>
    <div class='info-row'><div class='info-key'>执行状态</div><div class='info-val'>$(Html $diskModuleStatus)</div></div>
    $(if($diskTestEnabled -or $script:DiskModuleAttempted){
@"
    <div class='info-row'><div class='info-key'>磁盘总时长</div><div class='info-val'>$diskStageDisplay</div></div>
    <div class='info-row'><div class='info-key'>$($L.DiskTarget)</div><div class='info-val'>$(Html $diskTargets)</div></div>
    <div class='info-row'><div class='info-key'>测试组合</div><div class='info-val'>$(Html $diskProfileDisplay)</div></div>
    <div class='info-row'><div class='info-key'>时长分配</div><div class='info-val'>$(Html $diskPolicyText)</div></div>
    <div class='info-row'><div class='info-key'>顺序读写测试</div><div class='info-val'>$(Html $diskProbeText)</div></div>
    <div class='info-row'><div class='info-key'>说明</div><div class='info-val'>$(Html $diskModuleReasonDisplay)</div></div>
"@
    })
  </div>
</div>
"@
    $stageRows = ""
    if($script:GpuTestStatus -eq "PASS"){$stageRows += Stage-Row "gpu" $gpuRows}
    if($script:CpuModuleExecuted){$stageRows += Stage-Row "cpu" $cpuRows}
    if($script:DiskModuleExecuted -and $diskRows.Count -gt 0){ $stageRows += Stage-Row "disk 总计" $diskRows }
    if($script:DiskModuleExecuted -and $diskStabilityRows.Count -gt 0){ $stageRows += Stage-Row "disk 稳定性" $diskStabilityRows }
    if($script:DiskModuleExecuted -and $diskThroughputRows.Count -gt 0){ $stageRows += Stage-Row "disk 速度" $diskThroughputRows }
    if([string]::IsNullOrWhiteSpace($stageRows)){ $stageRows = "<tr><td colspan='4'>-</td></tr>" }
    $toolRows=""; foreach($t in $script:ToolInfo){ $module=$t.Module; if([string]::IsNullOrWhiteSpace($module)){ if($t.Tool -match "Disk"){$module=$L.DiskPressure} elseif($t.Tool -match "FurMark"){$module=$L.GpuPressure} elseif($t.Tool -match "y-cruncher"){$module=$L.CpuPressure} else {$module="Runtime"} }; $toolRows += "<tr><td>$module</td><td>$(Html $t.Tool)</td><td>$(Html $t.Source)</td><td>$(Html $t.Path)</td><td>$(Html $t.Args)</td></tr>" }
    if([string]::IsNullOrWhiteSpace($toolRows)){ $toolRows="<tr><td colspan='5'>-</td></tr>" }
    $sysInfo=""; $gpuInfo=""; $diskInfo=""; $script:CpuSummaryBox=""
    try{
        $cs=Get-CimInstance Win32_ComputerSystem; $os=Get-CimInstance Win32_OperatingSystem; $cpus=@(Get-CimInstance Win32_Processor); $cpu=$cpus[0]
        $vendor="Unknown"; if(($cpu.Name+$cpu.Manufacturer)-match "Intel"){$vendor="Intel"}elseif(($cpu.Name+$cpu.Manufacturer)-match "AMD"){$vendor="AMD"}
        $cpuSockets = $cpus.Count
        $cpuCores = (($cpus|Measure-Object NumberOfCores -Sum).Sum)
        $cpuThreads = (($cpus|Measure-Object NumberOfLogicalProcessors -Sum).Sum)
        $memGbText = (ToGB $cs.TotalPhysicalMemory)
        $script:CpuSummaryBox = "<div class='cpu-highlight'><div class='cpu-label'>$($L.CpuModelBig)</div><div class='cpu-model'>$(Html $cpu.Name)</div><div class='cpu-sub'>$($L.CpuVendor): <b>$(Html $vendor)</b> &nbsp; | &nbsp; $($L.CpuSockets): <b>$cpuSockets</b> &nbsp; | &nbsp; $($L.CpuCores): <b>$cpuCores</b> &nbsp; | &nbsp; $($L.CpuThreads): <b>$cpuThreads</b> &nbsp; | &nbsp; $($L.MemoryGB): <b>$memGbText GB</b></div></div>"
        $sysInfo += "$($L.ComputerName) : $(Html $env:COMPUTERNAME)<br>"
        $sysInfo += "$($L.OS) : $(Html (("{0} {1}" -f $os.Caption,$os.Version)))<br>"
        $sysInfo += "$($L.CpuVendor) : <b>$(Html $vendor)</b><br>"
        $sysInfo += "$($L.CPU) : <b>$(Html $cpu.Name)</b><br>"
        $sysInfo += "$($L.CpuSockets) : $cpuSockets<br>"
        $sysInfo += "$($L.CpuCores) : $cpuCores<br>"
        $sysInfo += "$($L.CpuThreads) : $cpuThreads<br>"
        $sysInfo += "$($L.MemoryGB) : $memGbText"
    }catch{$sysInfo="-"}
    try{ $g=& nvidia-smi --query-gpu=index,name,driver_version,temperature.gpu,fan.speed,power.draw,memory.used,memory.total --format=csv,noheader,nounits 2>$null; if($g){$gpuInfo=Html ($g -join "`r`n")} else {$gpuInfo="未检测到 NVIDIA GPU<br>GPU 压测：未测试<br>GPU 相关项目：全部跳过"} }catch{$gpuInfo="未检测到 NVIDIA GPU<br>GPU 压测：未测试<br>GPU 相关项目：全部跳过"}
    try{ $ds=Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3"|Sort-Object DeviceID|ForEach-Object{"{0} | Size {1} GB | Free {2} GB" -f $_.DeviceID,(ToGB $_.Size),(ToGB $_.FreeSpace)}; $diskInfo=Html ($ds -join "`r`n") }catch{$diskInfo="-"}
    $diskThresholdHtml = Get-DiskThresholdSummaryHtml
    $dynamicThresholdInfo=@()
    if($cpuPowerLimitAvailable) {
        $cpuPowerLimitDisplay = Html ("{0} W（LHM PPT/Power Limit 反推）" -f $cpuPowerLimitW)
        $dynamicThresholdInfo += "<div><b>CPU 动态功耗上限：</b>$cpuPowerLimitDisplay</div>"
    }
    if($gpuPowerLimitAvailable) {
        $gpuPowerLimitDisplay = Html ("{0} W（nvidia-smi power.limit 合计）" -f $gpuPowerLimitW)
        $dynamicThresholdInfo += "<div><b>GPU 动态功耗上限：</b>$gpuPowerLimitDisplay</div>"
    }
    if($gpuThermalLimitAvailable) {
        $gpuThermalLimitDisplay = Html ("{0} C（nvidia-smi GPU Slowdown Temp）" -f $gpuThermalSlowdownC)
        $dynamicThresholdInfo += "<div><b>GPU 动态热降频点：</b>$gpuThermalLimitDisplay</div>"
    }
    $dynamicThresholdHtml = [string]::Join('', [string[]]$dynamicThresholdInfo)
    $thresholdInfo = "<div class='threshold-summary'><div><b>CPU 参考类型：</b>$(Html $script:CpuThresholdProfile)</div><div><b>GPU 参考类型：</b>$(Html $script:GpuThresholdProfile)</div>$dynamicThresholdHtml</div><div class='threshold-subtitle'>磁盘性能参考</div>$diskThresholdHtml"
    $hwTable=@"
<div class='hw-grid'>
  <div class='hw-card hw-card-main'>$script:CpuSummaryBox</div>
  <div class='hw-card'><div class='card-title'>系统信息</div><div class='pre compact'>$sysInfo</div></div>
  <div class='hw-card'><div class='card-title'>$($L.GpuInfo)</div><div class='pre compact'>$gpuInfo</div></div>
  <div class='hw-card'><div class='card-title'>$($L.DiskInfo)</div><div class='pre compact'>$diskInfo</div></div>
</div>
<div class='threshold-panel'><div class='card-title'>本机测试参考标准</div>$thresholdInfo</div>
"@
    $criteria=""
    $cpuCriteria = CriteriaCell `
        "<ul class='mini-list'><li>最大负载 ≥ 80%</li><li>稳定窗口平均 ≥ 50%</li><li>CPU 温度 &lt; ${CpuTempFailC} C</li></ul>" `
        "<ul class='mini-list'><li>低于严格参考只记录说明</li><li>短测/启动/停止窗口波动不直接判失败</li></ul>" `
        "<ul class='mini-list'><li>CPU 温度 ≥ ${CpuTempFailC} C</li><li>最大负载 &lt; 80%</li><li>稳定窗口平均 &lt; 50%</li><li>崩溃、重启、压测进程失败</li></ul>"
    $criteria += "<tr><td><b>CPU</b><br><span class='muted'>$script:CpuThresholdProfile</span></td><td>$cpuCriteria</td><td>稳定窗口会跳过启动、fallback、停止阶段采样；Server CPU 优先使用 IPMI/CPU_TEMP 传感器。</td></tr>"

    $memCriteria = CriteriaCell `
        "<ul class='mini-list'><li>y-cruncher 按目标内存比例运行</li><li>测试完成且无 OOM / hang / reboot</li><li>达到目标内存策略附近即可通过</li></ul>" `
        "<ul class='mini-list'><li>实际内存使用低于目标时记录说明</li><li>短时间启动/停止窗口波动不直接判失败</li></ul>" `
        "<ul class='mini-list'><li>内存压力未达到预期</li><li>OOM、卡死、重启</li></ul>"
    $criteria += "<tr><td><b>Memory</b><br><span class='muted'>Detected system memory</span></td><td>$memCriteria</td><td>目标：y-cruncher 内存策略 ${YCruncherMemoryPercent}%；CPU阶段由 y-cruncher 单独负责 CPU + Memory 压力。</td></tr>"

    $gpuPowerPassCriteria = if($gpuPowerLimitAvailable){"<li>平均总功耗 ≥ $([math]::Round($gpuPowerLimitW*0.70,2)) W（驱动上限的 70%）</li>"}else{"<li>未读取到驱动功耗上限，平均功耗不参与判定</li>"}
    $gpuPowerWarnCriteria = if($gpuPowerLimitAvailable){"<li>平均总功耗为驱动上限的 50%–70%</li>"}else{"<li>功耗传感器可记录，但不参与平均功耗判定</li>"}
    $gpuPowerFailCriteria = if($gpuPowerLimitAvailable){"<li>平均总功耗 &lt; $([math]::Round($gpuPowerLimitW*0.50,2)) W（驱动上限的 50%）</li>"}else{"<li>无可验证的驱动功耗上限</li>"}
    $gpuTempPassCriteria = if($gpuThermalLimitAvailable){"<li>平均最高温度 &lt; $([math]::Round($gpuThermalSlowdownC-10,1)) C（热降频点预留 10 C）</li>"}else{"<li>平均最高温度按 GPU 温度阈值评定</li>"}
    $gpuTempWarnCriteria = if($gpuThermalLimitAvailable){"<li>平均最高温度距热降频点不足 10 C</li>"}else{"<li>平均最高温度达到 GPU 温度关注阈值</li>"}
    $gpuTempFailCriteria = if($gpuThermalLimitAvailable){"<li>平均最高温度 ≥ ${gpuThermalSlowdownC} C（驱动热降频点）</li>"}else{"<li>平均最高温度达到 GPU 温度不合格阈值</li>"}
    $gpuCriteria = CriteriaCell `
        "<ul class='mini-list'><li>GPU 最大利用率 ≥ 80%</li><li>GPU 温度 &lt; ${GpuTempFailC} C</li>$gpuTempPassCriteria$gpuPowerPassCriteria</ul>" `
        "<ul class='mini-list'><li>平均负载低于严格参考时记录说明</li>$gpuTempWarnCriteria$gpuPowerWarnCriteria</ul>" `
        "<ul class='mini-list'><li>GPU 温度 ≥ ${GpuTempFailC} C</li>$gpuTempFailCriteria$gpuPowerFailCriteria<li>最大利用率 &lt; 80%</li><li>驱动重置、黑屏、崩溃、GPU 消失</li></ul>"
    $criteria += "<tr><td><b>GPU</b><br><span class='muted'>$script:GpuThresholdProfile</span></td><td>$gpuCriteria</td><td>Detected GPU: $(HtmlE $script:DetectedGpuNameForThreshold)。有效平均只统计有负载样本；风扇只作为散热参考。</td></tr>"

    $fanCriteria = CriteriaCell `
        "<ul class='mini-list'><li>温度处于允许范围</li><li>支持风扇遥测时可记录转速</li></ul>" `
        "<ul class='mini-list'><li>高温但风扇偏低</li><li>风扇速度 N/A</li></ul>" `
        "<ul class='mini-list'><li>温度上升但风扇 0% / 停转</li><li>传感器确认散热异常</li></ul>"
    $criteria += "<tr><td><b>Cooling / Fan</b></td><td>$fanCriteria</td><td>GPU 风扇来自 nvidia-smi fan.speed；系统风扇依赖主板/BMC 支持。</td></tr>"

    $diskCriteria = CriteriaCell `
        "<ul class='mini-list'><li>测试完整结束并获得有效结果</li><li>4K 随机读写和顺序读写达到相应参考值</li><li>未发现 I/O 错误、坏块、掉盘或测试中断</li></ul>" `
        "<ul class='mini-list'><li>测试结果有效，但性能低于参考值</li><li>自动汇总未识别结果，需要结合原始日志复核</li><li>部分阵列或存储控制器环境只显示逻辑磁盘名称，此情况本身不代表硬盘异常</li></ul>" `
        "<ul class='mini-list'><li>出现 I/O 错误、坏块、掉盘或测试中断</li><li>未生成有效测试结果</li><li>性能严重异常，明显低于该类磁盘的合理性能范围</li></ul>"
    $criteria += "<tr><td><b>Disk</b><br><span class='muted'>按盘符分别测试</span></td><td>$diskCriteria</td><td>4K 随机读写主要看每秒读写次数（IOPS）和响应时间；顺序读写主要看读取速度、写入速度和综合读写速度。</td></tr>"
    $statusRows=""; foreach($s in $script:StatusItems){
        $part=if($s.Participate){$L.Yes}else{$L.No}
        $reasonText = if($s.Status -eq "NOT_TESTED"){ "-" } else { HtmlListFromText $s.Reason }
        $statusRows += "<tr><td><b>$($s.Item)</b></td><td>$(StatusBadge $s.Status)</td><td>$reasonText</td><td>$part</td></tr>"
    }
    if([string]::IsNullOrWhiteSpace($statusRows)){ $statusRows = "<tr><td colspan='4'>-</td></tr>" }
    function KeyMetricRow($item,$result,$judge){ return "<tr><td><b>$item</b></td><td>$(HtmlPipeList $result)</td><td>$judge</td></tr>" }
    # Customer-facing terminology policy:
    # - Module/project status: 通过 / 关注 / 不合格 / 未测试
    # - Individual metric judgement: 通过 / 关注 / 不合格 / 仅记录 / 未采集
    $judgeOk = "<span class='pass'>&#x901A;&#x8FC7;</span>"
    $judgePass = $judgeOk
    $judgeFullPass = $judgeOk
    $judgeAccept = "<span class='warn'>&#x5173;&#x6CE8;</span>"
    $judgeNote = "<span class='na'>&#x4EC5;&#x8BB0;&#x5F55;</span>"
    $judgeBad = "<span class='fail'>&#x4E0D;&#x5408;&#x683C;</span>"
    $judgeWarn = "<span class='warn'>&#x5173;&#x6CE8;</span>"
    $cpuMaxJudge = if($cpuMax -ne $null -and $cpuMax -ge 80){$judgeOk}else{$judgeBad}
    $cpuAvgJudge = if($cpuAvg -ne $null -and $cpuAvg -ge 50){$judgeOk}else{$judgeBad}
    $cpuTempJudge = if($cpuTemp -eq $null){"<span class='na'>&#x672A;&#x91C7;&#x96C6;&#xFF0C;&#x4E0D;&#x53C2;&#x4E0E;&#x5224;&#x5B9A;</span>"}elseif($cpuTemp -ge $CpuTempFailC){$judgeBad}elseif($cpuTemp -ge $CpuTempWarnC){$judgeAccept}else{$judgeOk}
    $cpuPowerTelemetryNA = "<span class='na'>-</span>"
    $cpuPowerBelowBaselineJudge = "<span class='na'>-</span>"
    $cpuPowerMaxJudge = if(!$cpuPowerAvailable -or !$cpuPowerBaselineAvailable){$cpuPowerTelemetryNA}elseif($cpuPower -ge $cpuPowerBaselineW){$judgeOk}else{$cpuPowerBelowBaselineJudge}
    $cpuPowerAvgJudge = if(!$cpuPowerAvgAvailable -or !$cpuPowerBaselineAvailable){$cpuPowerTelemetryNA}elseif($cpuPowerAvg -ge $cpuPowerBaselineW){$judgeOk}else{$cpuPowerBelowBaselineJudge}
    $memJudge = if($memMax -ne $null -and $memMax -ge 95){$judgeFullPass}elseif($memMax -ne $null -and $memMax -ge 40){$judgePass}else{$judgeBad}
    $gpuTelemetryNA = "<span class='na'>&#x672A;&#x91C7;&#x96C6;&#xFF0C;&#x4E0D;&#x53C2;&#x4E0E;&#x5224;&#x5B9A;</span>"
    $gpuMaxJudge = if(!$gpuUtilAvailable){$gpuTelemetryNA}elseif($gpuUtil -ge 80){$judgeOk}else{$judgeBad}
    $gpuAvgJudge = if(!$gpuUtilAvgAvailable){$gpuTelemetryNA}elseif($gpuUtilAvg -ge 80){$judgeOk}elseif($gpuUtilAvg -ge 50){$judgeAccept}else{$judgeBad}
    $gpuTempJudge = if($gpuTemp -eq $null){$judgeNote}elseif($gpuTemp -ge $GpuTempFailC){$judgeBad}elseif($gpuTemp -ge $GpuTempWarnC){$judgeAccept}else{$judgeOk}
    $gpuTempAvgJudge = if($gpuTempAvg -eq $null){$gpuTelemetryNA}elseif($gpuThermalLimitAvailable -and $gpuTempAvg -ge $gpuThermalSlowdownC){$judgeBad}elseif($gpuThermalLimitAvailable -and $gpuTempAvg -ge ($gpuThermalSlowdownC - 10)){$judgeAccept}elseif(!$gpuThermalLimitAvailable -and $gpuTempAvg -ge $GpuTempFailC){$judgeBad}elseif(!$gpuThermalLimitAvailable -and $gpuTempAvg -ge $GpuTempWarnC){$judgeAccept}else{$judgeOk}
    $gpuFanJudge = if($gpuFan -eq $null){"<span class='na'>&#x672A;&#x91C7;&#x96C6;&#xFF0C;&#x4E0D;&#x53C2;&#x4E0E;&#x5224;&#x5B9A;</span>"}else{$judgeOk}
    $gpuPowerJudge = if(!$gpuPowerAvailable){$gpuTelemetryNA}elseif($gpuPower -ge $GpuPowerPassW){$judgeOk}else{$judgeAccept}
    $gpuPowerAvgJudge = if(!$gpuPowerAvgAvailable){$gpuTelemetryNA}elseif(!$gpuPowerLimitAvailable){$judgeNote}elseif($gpuPowerAvg -ge ($gpuPowerLimitW * 0.70)){$judgeOk}elseif($gpuPowerAvg -ge ($gpuPowerLimitW * 0.50)){$judgeAccept}else{$judgeBad}
    $diskJudge = if($diskModuleState -eq "PASS"){$judgeOk}elseif($diskModuleState -eq "WARN"){$judgeWarn}else{$judgeBad}
    $metrics=""
    $metrics += "<tr><th>&#x9879;&#x76EE;</th><th>&#x7ED3;&#x679C;</th><th>&#x5224;&#x65AD;</th></tr>"
    $metrics += KeyMetricRow "&#x811A;&#x672C;&#x6784;&#x5EFA;&#x7248;&#x672C;" $ScriptBuild $judgeNote
    if($cpuTestEnabled){
        $metrics += KeyMetricRow "CPU &#x6700;&#x5927;&#x4F7F;&#x7528;&#x7387;" (FmtVal $cpuMax '%') $cpuMaxJudge
        $metrics += KeyMetricRow "CPU &#x7A33;&#x5B9A;&#x7A97;&#x53E3;&#x5E73;&#x5747;" (FmtVal $cpuAvg '%') $cpuAvgJudge
        $metrics += KeyMetricRow "CPU &#x6700;&#x9AD8;&#x6E29;&#x5EA6;" (FmtVal $cpuTemp 'C') $cpuTempJudge
        $metrics += KeyMetricRow "CPU &#x5E73;&#x5747;&#x6E29;&#x5EA6;" (FmtVal $cpuTempAvg 'C') $cpuTempJudge
        $metrics += KeyMetricRow "CPU &#x6700;&#x5927;&#x529F;&#x8017;" (FmtVal $cpuPower 'W') $cpuPowerMaxJudge
        $metrics += KeyMetricRow "CPU &#x5E73;&#x5747;&#x529F;&#x8017;" (FmtVal $cpuPowerAvg 'W') $cpuPowerAvgJudge
        $metrics += KeyMetricRow "&#x5185;&#x5B58;&#x6700;&#x5927;&#x4F7F;&#x7528;&#x7387;" (FmtVal $memMax '%') $memJudge
    }
    if($gpuDetected -and $gpuTestEnabled){
        $metrics += KeyMetricRow "GPU &#x6700;&#x5927;&#x4F7F;&#x7528;&#x7387;" (FmtVal $gpuUtil '%') $gpuMaxJudge
        $metrics += KeyMetricRow "GPU &#x6709;&#x6548;&#x5E73;&#x5747;&#x4F7F;&#x7528;&#x7387;" (FmtVal $gpuUtilAvg '%') $gpuAvgJudge
        $metrics += KeyMetricRow "GPU &#x6700;&#x9AD8;&#x6E29;&#x5EA6;" (FmtVal $gpuTemp 'C') $gpuTempJudge
        $metrics += KeyMetricRow "GPU &#x5E73;&#x5747;&#x6700;&#x9AD8;&#x6E29;&#x5EA6;" (FmtVal $gpuTempAvg 'C') $gpuTempAvgJudge
        $metrics += KeyMetricRow "GPU &#x98CE;&#x6247;&#x6700;&#x9AD8;" (FmtVal $gpuFan '%') $gpuFanJudge
        $metrics += KeyMetricRow "GPU &#x6700;&#x5927;&#x529F;&#x8017;" (FmtVal $gpuPower 'W') $gpuPowerJudge
        $metrics += KeyMetricRow "GPU &#x5E73;&#x5747;&#x603B;&#x529F;&#x8017;" (FmtVal $gpuPowerAvg 'W') $gpuPowerAvgJudge
    }
    if($diskTestEnabled){
        foreach($dmr in $diskMetricItems){
            $dmJudge = if($dmr.State -eq "PASS"){$judgeOk}elseif($dmr.State -eq "WARN"){$judgeWarn}else{$judgeBad}
            $metrics += KeyMetricRow $dmr.Name $dmr.Result $dmJudge
        }
    }
    function MetricItem($label,$value){ return "<div class='metric-row'><div class='metric-key'>$(Html $label)</div><div class='metric-val'>$value</div></div>" }
    function PhaseMetricCard($title,$items){
        if($items.Count -eq 0){ return "" }
        $body = ($items -join "")
        return "<div class='stage-card'><div class='stage-card-title'>$(Html $title)</div>$body</div>"
    }
    $stageMetricCards = ""
    if($gpuRows.Count -gt 0){
        $gpuItems=@()
        $gpuItems += MetricItem "GPU 最大利用率" (FmtVal (Get-Max $gpuRows 'GPU_Util_Max_Percent') '%')
        $gpuItems += MetricItem "GPU 最高温度" (FmtVal (Get-Max $gpuRows 'GPU_Temp_Max_C') 'C')
        $gpuItems += MetricItem "GPU 平均最高温度" (FmtVal $gpuTempAvg 'C')
        $gpuItems += MetricItem "GPU 风扇最高" (FmtVal (Get-Max $gpuRows 'GPU_Fan_Max_Percent') '%')
        $gpuItems += MetricItem "GPU 最大功耗" (FmtVal (Get-Max $gpuRows 'GPU_Power_Total_W') 'W')
        $gpuItems += MetricItem "GPU 平均总功耗" (FmtVal $gpuPowerAvg 'W')
        $stageMetricCards += PhaseMetricCard "GPU 阶段汇总" $gpuItems
    }
    if($cpuRows.Count -gt 0){
        $cpuItems=@()
        $cpuItems += MetricItem "CPU 最大使用率" (FmtVal (Get-Max $cpuRows 'CPU_Percent') '%')
        $cpuItems += MetricItem "CPU 最高温度" (FmtVal (Get-Max $cpuRows 'CPU_Temperature_C') 'C')
        $cpuItems += MetricItem "CPU 平均温度" (FmtVal (Get-Avg $cpuRows 'CPU_Temperature_C') 'C')
        $cpuItems += MetricItem "CPU 最大功耗" (FmtVal (Get-Max $cpuRows 'CPU_Package_Power_W') 'W')
        $cpuItems += MetricItem "CPU 平均功耗" (FmtVal (Get-Avg $cpuJudgeRows 'CPU_Package_Power_W') 'W')
        $cpuItems += MetricItem "CPU 最高频率" (FmtVal (Get-Max $cpuRows 'CPU_Clock_Current_MHz') 'MHz')
        $cpuItems += MetricItem "内存最高使用率" (FmtVal (Get-Max $cpuRows 'Memory_Used_Percent') '%')
        $stageMetricCards += PhaseMetricCard "CPU / 内存阶段汇总" $cpuItems
    }
    if($diskTestEnabled){
        $diskItems=@()
        foreach($dsi in @($diskStageSummaryItems)){
            $diskItems += MetricItem $dsi.Label (HtmlPipeList $dsi.Value)
        }
        if($diskItems.Count -eq 0){
            $diskItems += MetricItem "状态" "没有可显示的磁盘测试结果"
        }
        $stageMetricCards += PhaseMetricCard "磁盘阶段汇总" $diskItems
    }
    if([string]::IsNullOrWhiteSpace($stageMetricCards)){$stageMetricCards="<div class='stage-card'><div class='stage-card-title'>分项指标汇总</div><div class='metric-row'><div class='metric-key'>状态</div><div class='metric-val'>-</div></div></div>"}
    function ChartBlock($label,$file){ $path=Join-Path $ChartDir $file; if(Test-Path $path){ return "<h3>$label</h3><div class='chart'><object data='charts/$file' type='image/svg+xml'></object></div>" }; return "" }
    $charts=""; if($gpuDetected -and $gpuEnabled){ $charts += ChartBlock $L.GpuUtilChart "gpu_util.svg"; $charts += ChartBlock $L.GpuTempChart "gpu_temp.svg"; $charts += ChartBlock "GPU Fan Speed" "gpu_fan.svg"; $charts += ChartBlock $L.GpuPowerChart "gpu_power.svg"; $charts += ChartBlock $L.GpuMemChart "gpu_memory.svg" }
    $charts += ChartBlock $L.CpuUtilChart "cpu_percent.svg"; $charts += ChartBlock $L.CpuClockChart "cpu_clock.svg"; $charts += ChartBlock $L.CpuTempChart "cpu_temp.svg"; $charts += ChartBlock $L.CpuPowerChart "cpu_power.svg"; $charts += ChartBlock $L.MemChart "memory_percent.svg"; $charts += ChartBlock $L.DiskReadChart "disk_read.svg"; $charts += ChartBlock $L.DiskWriteChart "disk_write.svg"
    $rawRows=""
    $rawRows += "<tr><th>$($L.SampleCsv)</th><td>$(Html $MonitorCsv)</td></tr>"
    $rawRows += "<tr><th>$($L.GpuCsv)</th><td>$(Html $GpuSmiCsv)</td></tr>"
    $rawRows += "<tr><th>$($L.CpuSensorCsv)</th><td>$(Html $CpuSensorCsv)</td></tr>"
    $rawRows += "<tr><th>$($L.MemoryLog)</th><td>$(Html (Join-Path $LogDir 'memory_stress.log'))</td></tr>"
    $rawRows += "<tr><th>$($L.EventLog)</th><td>$(Html $EventLog)</td></tr>"
    $html=@"
<!doctype html>
<html><head><meta charset="utf-8"><title>$($L.Title)</title>
<style>
@page { size: A4; margin: 12mm; }
body { font-family: "Microsoft YaHei", "Segoe UI", Arial, sans-serif; color:#1f2937; background:white; margin:42px; font-size:13px; line-height:1.55; }
h1 { color:#1f4e79; font-size:28px; line-height:1.25; margin:20px 0 8px; }
h2 { color:#1f4e79; font-size:20px; margin:26px 0 12px; padding-left:10px; border-left:5px solid #1f4e79; }
h3 { color:#111827; font-size:15px; margin:20px 0 8px; }
.small,.muted { color:#6b7280; font-size:12px; }
table { border-collapse:collapse; width:100%; margin:8px 0 18px; table-layout:fixed; }
th,td { border:1px solid #d6dbe3; padding:9px 11px; vertical-align:top; word-break:break-word; }
th { background:#f5f7fa; text-align:left; font-weight:700; }
.pass { color:#008000; font-weight:700; } .warn { color:#b45309; font-weight:700; } .fail { color:#b91c1c; font-weight:700; } .na { color:#6b7280; font-weight:700; }
.conclusion { border:1px solid #d6dbe3; padding:12px 14px; background:#fbfdff; margin:12px 0 20px; }
.pre { white-space:pre-wrap; font-family:Consolas, "Microsoft YaHei", monospace; font-size:12px; line-height:1.55; }
.compact { line-height:1.45; }
.hw-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin:8px 0 12px; }
.hw-card,.threshold-panel { border:1px solid #d6dbe3; background:#fbfdff; border-radius:6px; padding:12px 14px; }
.hw-card-main { background:#f3f8fd; border-color:#93b7dc; }
.card-title { color:#1f4e79; font-weight:800; margin-bottom:8px; font-size:14px; }
.threshold-panel { margin:12px 0 18px; background:#fff; }
.info-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin:8px 0 18px; }
.info-card { border:1px solid #d6dbe3; background:#fbfdff; border-radius:6px; padding:12px 14px; }
.info-card.span-2 { grid-column:1 / span 2; }
.info-row { display:flex; justify-content:space-between; align-items:flex-start; gap:18px; padding:6px 0; border-bottom:1px dashed #e5e7eb; }
.info-row:last-child { border-bottom:0; }
.info-key { color:#4b5563; font-weight:700; min-width:120px; }
.info-val { color:#111827; flex:1; text-align:right; word-break:break-word; }
.stage-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin:8px 0 18px; }
.stage-card { border:1px solid #d6dbe3; background:#fbfdff; border-radius:6px; padding:12px 14px; }
.stage-card-title { color:#1f4e79; font-weight:800; margin-bottom:8px; font-size:14px; }
.metric-row { display:flex; justify-content:space-between; gap:16px; padding:7px 0; border-bottom:1px dashed #e5e7eb; }
.metric-row:last-child { border-bottom:0; }
.metric-key { color:#4b5563; font-weight:700; }
.metric-val { color:#111827; text-align:right; }
.metric-val .metric-list { text-align:left; display:inline-block; }
.criteria-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }
.criteria-grid > div { background:#fbfdff; border:1px solid #edf1f7; border-radius:5px; padding:8px; }
.status-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; margin:8px 0 18px; }
.status-card { border:1px solid #d6dbe3; background:#fbfdff; border-radius:6px; padding:12px 14px; }
.status-head { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; margin-bottom:8px; }
.status-title { color:#1f4e79; font-weight:800; font-size:15px; }
.status-badge-wrap { flex-shrink:0; }
.status-body { color:#111827; line-height:1.6; }
.status-foot { margin-top:10px; padding-top:8px; border-top:1px dashed #e5e7eb; display:flex; justify-content:space-between; gap:12px; }
.status-foot-key { color:#4b5563; font-weight:700; }
.status-foot-val { color:#111827; }
.disk-guide { border:1px solid #93b7dc; background:#f3f8fd; border-radius:6px; padding:11px 13px; margin:8px 0 12px; line-height:1.65; }
.disk-result-table td { line-height:1.55; }
.disk-result-table td:nth-child(4), .disk-result-table td:nth-child(5) { font-size:12.5px; }
.disk-result-table .result-line { display:flex; justify-content:space-between; gap:12px; padding:3px 0; border-bottom:1px dashed #e5e7eb; }
.disk-result-table .result-line:last-of-type { border-bottom:0; }
.disk-result-table .result-line span { color:#4b5563; }
.disk-result-table .result-line b { color:#111827; white-space:nowrap; }
.disk-result-table .result-total { margin-top:3px; padding-top:5px; font-weight:700; }
.result-note { color:#6b7280; font-size:11.5px; margin-top:5px; line-height:1.45; }
.reference-main { font-weight:700; color:#1f4e79; margin-bottom:4px; }
.disk-judge { text-align:center; vertical-align:middle; }
.disk-reference-table { margin:7px 0 8px; }
.disk-reference-table th,.disk-reference-table td { padding:7px 9px; }
.threshold-summary { display:flex; gap:28px; flex-wrap:wrap; margin-bottom:8px; }
.threshold-subtitle { color:#1f4e79; font-weight:800; margin:8px 0 4px; }
.criteria-title { font-weight:800; margin-bottom:5px; }
.mini-list,.reason-list,.metric-list { margin:0; padding-left:18px; }
.mini-list li,.reason-list li,.metric-list li { margin:2px 0; }
.status-table td:nth-child(3), .criteria-table td:nth-child(2) { line-height:1.55; }
.chart { border:1px solid #e5e7eb; padding:10px; margin-bottom:18px; }
.chart object { width:100%; height:270px; }
.footer { font-size:12px; color:#374151; margin-top:24px; }
.cpu-highlight { border:0; background:transparent; padding:0; border-radius:4px; }
.cpu-label { color:#1f4e79; font-size:13px; font-weight:700; margin-bottom:4px; }
.cpu-model { color:#0f172a; font-size:22px; line-height:1.25; font-weight:800; margin-bottom:6px; }
.cpu-sub { color:#374151; font-size:13px; }
@media print { body { margin:24px; } .hw-grid,.info-grid,.criteria-grid,.stage-grid,.status-grid { display:block; } .hw-card,.info-card,.criteria-grid>div,.stage-card,.status-card { margin-bottom:8px; } .info-row,.metric-row,.status-foot { display:block; } .info-val,.metric-val,.status-foot-val { text-align:left; margin-top:2px; } }
</style></head><body>
<h1>$($L.Title)</h1>
<div class='small'>$($L.ReportDir): $(Html $ReportRoot)</div>
<h2>$($L.Sec1)</h2>
<div class='conclusion'><b>$($L.Overall):</b> $(StatusBadge $overall)<br><b>$($L.Conclusion):</b> $note</div>
<h2>$($L.Sec5)</h2>$hwTable
<h2>$($L.Sec2)</h2>$testInfoCards
<h2>$($L.Sec3)</h2><table><tr><th>$($L.Phase)</th><th>$($L.PhaseStart)</th><th>$($L.PhaseEnd)</th><th>$($L.Duration)</th></tr>$stageRows</table>
<h2>$($L.SecCriteria)</h2><table class='criteria-table'><tr><th style='width:18%'>$($L.Metric)</th><th>判定规则</th><th style='width:24%'>$($L.Remark)</th></tr>$criteria</table>
<h2>$($L.SecStatus)</h2><table class='status-table'><tr><th style='width:22%'>$($L.Item)</th><th style='width:10%'>$($L.Status)</th><th>$($L.MainResult)</th><th style='width:10%'>$($L.Participate)</th></tr>$statusRows</table>
<h2>$($L.SecDiskResult)</h2>$diskResultTableHtml
<h2>$($L.SecMetrics)</h2><table>$metrics</table>
<h2>$($L.SecStageMetrics)</h2><div class='stage-grid'>$stageMetricCards</div>
<h2>$($L.SecCharts)</h2><p class='small'>$($L.ChartNote)</p>$charts
<h2>$($L.SecRaw)</h2><table>$rawRows</table>
<h2>$($L.Sec4)</h2><table><tr><th>$($L.Module)</th><th>$($L.Tool)</th><th>$($L.Backend)</th><th>$($L.ToolPath)</th><th>$($L.KeyArgs)</th></tr>$toolRows</table>
<div class='footer'><p><b>$($L.Description):</b> $($L.FooterDesc)</p><p><b>$($L.Scope):</b> $($L.FooterScope)</p></div>
</body></html>
"@
    $html | Out-File $HtmlReport -Encoding UTF8
    "Overall=$overall`r`nReport=$HtmlReport`r`nZip=$ZipPath" | Out-File $SummaryTxt -Encoding UTF8
    Log "[报告生成] HTML报告已生成: $HtmlReport"
}

function Write-Zip {
    try { if(Test-Path $ZipPath){Remove-Item $ZipPath -Force}; Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::CreateFromDirectory($ReportRoot,$ZipPath); Log "[ZIP] $ZipPath" } catch { Log "[WARN] ZIP failed: $($_.Exception.Message)" }
}

Log "============================================================"
Log ("Windows Stress Report {0} started" -f $ScriptBuild)
Log "ReportRoot: $ReportRoot"
Log "Mode: $Mode"
Log "TestAllFixedDrives: $TestAllFixedDrives"
Log "DiskFileSize: $DiskFileSize"
Log "DiskIoProfile: $DiskIoProfile"
Log "DiskThroughputProbeSeconds: $DiskThroughputProbeSeconds"
Log "DiskBothTimePolicy: $DiskBothTimePolicy"
Log "CleanupDiskSpdTempFiles: $CleanupDiskSpdTempFiles"
Log "CleanupAllFixedDrives: $CleanupAllFixedDrives"
Log "GpuBackend: $GpuBackend"
Log "CpuMemBackend: $CpuMemBackend"
Log "AutoHardwareThreshold: $AutoHardwareThreshold"
Log "MergeBaseReportDir: $script:MergeBaseReportDir"
Log "SupplementMergeMode: $script:SupplementMergeMode"
Log "CpuThresholdProfile: $script:CpuThresholdProfile"
Log "GpuThresholdProfile: $script:GpuThresholdProfile"
Log "DiskThresholdProfile: $script:DiskThresholdProfile"
Log "EnableCpuTemperature: $EnableCpuTemperature"
Log "EnableCpuPower: $EnableCpuPower"
Log "GpuPowerPassW: $GpuPowerPassW"
Log "GpuFanFullPercent: $GpuFanFullPercent"
Log "============================================================"

Log "[START] Stress workflow initialization completed."
Pause-WindowsUpdateForStress
Log "[START] Hardware detection and test preparation..."

$script:ResolvedTestDrives = Resolve-TestDrives
Assert-TestDrives $script:ResolvedTestDrives
Initialize-DiskDriveProfiles $script:ResolvedTestDrives
Log "DiskThresholdProfile: $script:DiskThresholdProfile"
Write-MonitorHeader
Initialize-CpuTemperatureCollector

try {
    Stage-Message "[运行] 开始执行选择的压力测试任务..."`n    Log "[RUN] Starting selected stress workload..."

    Stage-Message "[准备] 正在准备压测工具..."
    Initialize-StressToolPreparation
    Stage-Message "[完成] 压测工具准备完成，开始正式压力测试"
    if ($FastScanOnly) { Log "[FASTSCAN] Tool scan only." }
    elseif ($AllHours -gt 0) {
        $totalSeconds=[int]($AllHours*3600)
        if($DiskIoProfile -eq "both" -and $DiskBothTimePolicy -eq "split") { Log "[WARN] DiskBothTimePolicy=split is designed for staged/disk modes. Mode=all keeps the original all-phase duration and appends the throughput probe." }
        Run-Phase "all" $totalSeconds $true $true (!$script:SkipDiskPhase)
        Invoke-DiskThroughputProbeIfNeeded
    }
    elseif ($Mode -eq "staged") {
        Run-Phase "gpu" ([int]($GpuMinutes*60)) $true $false $false
        Run-Phase "cpu" ([int]($CpuMinutes*60)) $false $true $false
        $diskTotalSeconds=[int][math]::Round($DiskMinutes*60)
        $diskPlan=Get-DiskBothSplitDurations $diskTotalSeconds
        if($DiskIoProfile -eq "both") { Log ("[DISK PLAN] TotalSeconds={0}; StabilitySeconds={1}; ThroughputSeconds={2}; Policy={3}" -f $diskTotalSeconds,$diskPlan.StabilitySeconds,$diskPlan.ThroughputSeconds,$diskPlan.Policy) }
        Run-Phase "disk" $diskPlan.StabilitySeconds $false $false (!$script:SkipDiskPhase)
        Invoke-DiskThroughputProbeIfNeeded $diskPlan.ThroughputSeconds
    } elseif ($Mode -eq "gpu") { $dur = if($GpuMinutes -gt 0){[int]($GpuMinutes*60)}else{[int]($DurationHours*3600)}; Run-Phase "gpu" $dur $true $false $false }
    elseif ($Mode -eq "cpu") { $dur = if($CpuMinutes -gt 0){[int]($CpuMinutes*60)}else{[int]($DurationHours*3600)}; Run-Phase "cpu" $dur $false $true $false }
    elseif ($Mode -eq "disk") {
        $diskTotalSeconds = if($DiskMinutes -gt 0){[int][math]::Round($DiskMinutes*60)}else{[int]($DurationHours*3600)}
        $diskPlan=Get-DiskBothSplitDurations $diskTotalSeconds
        if($DiskIoProfile -eq "both") { Log ("[DISK PLAN] TotalSeconds={0}; StabilitySeconds={1}; ThroughputSeconds={2}; Policy={3}" -f $diskTotalSeconds,$diskPlan.StabilitySeconds,$diskPlan.ThroughputSeconds,$diskPlan.Policy) }
        Run-Phase "disk" $diskPlan.StabilitySeconds $false $false (!$script:SkipDiskPhase)
        Invoke-DiskThroughputProbeIfNeeded $diskPlan.ThroughputSeconds
    }
    elseif ($Mode -eq "all") {
        if($DiskIoProfile -eq "both" -and $DiskBothTimePolicy -eq "split") { Log "[WARN] DiskBothTimePolicy=split is designed for staged/disk modes. Mode=all keeps the original all-phase duration and appends the throughput probe." }
        Run-Phase "all" ([int]($DurationHours*3600)) $true $true (!$script:SkipDiskPhase)
        Invoke-DiskThroughputProbeIfNeeded
    }
} finally {
    Stage-Message "[报告] 正在生成测试报告..."`n    Log "[压测完成] 所有测试阶段已结束，正在整理并生成最终报告..."
    Merge-BaseReportNonDiskSamples
    Build-Report
    Write-Zip
    Stage-Message "[完成] 所有测试完成"`n    Log "[完成] HTML报告位置: $HtmlReport"
    Log "[完成] 压测报告压缩包位置: $ZipPath"
}
