import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import script_library
from app.core.task_runner import TaskRunnerError, _resolve_task_library_file


class WindowsScriptLibraryTests(unittest.TestCase):
    def test_latest_windows_stress_script_is_v100(self) -> None:
        windows_root = Path(__file__).resolve().parents[1] / "scripts" / "windows"

        self.assertTrue((windows_root / "v100_windows_stress.ps1").is_file())
        self.assertFalse((windows_root / "v99_windows_stress.ps1").exists())

    def test_v100_windows_stress_repairs_outdated_vc_runtime_before_y_cruncher(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1").read_text(encoding="utf-8-sig")

        self.assertIn('$MinimumVCRedistVersion = [version]"14.51.36247.0"', content)
        self.assertIn('System32\\MSVCP140.dll', content)
        self.assertIn('https://aka.ms/vc14/vc_redist.x64.exe', content)
        self.assertIn('https://aka.ms/vc14/vc_redist.x86.exe', content)
        self.assertIn('Get-AuthenticodeSignature -FilePath $installer.FullName', content)
        self.assertIn('Start-Process -FilePath $installer', content)
        self.assertIn('[VCREDIST] Verified MSVCP140.dll version:', content)
        self.assertIn('if (!(Ensure-VCRuntime))', content)

    def test_v100_windows_stress_starts_cpu_duration_only_after_y_cruncher_is_ready(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1").read_text(encoding="utf-8-sig")

        self.assertIn('[int]$YCruncherPreparationTimeoutSeconds = 900', content)
        self.assertIn('function Wait-YCruncherReady', content)
        self.assertIn('$readyCpuPercent = 80', content)
        self.assertIn('$readyMemoryPercent = [math]::Max(1, $YCruncherMemoryPercent - 5)', content)
        self.assertIn('if (!(Wait-YCruncherReady $ycProcessIds $DurationSeconds))', content)
        self.assertIn('y-cruncher preparation timed out before effective CPU/memory stress started', content)
        self.assertIn('EPYC 9V', content)
        self.assertIn('function Wait-YCruncherReady([int[]]$ProcessIds,[int]$PhaseDurationSeconds)', content)
        self.assertIn('Get-Process -Id $processId', content)
        self.assertIn('$lastPreparationMemoryBucket = -1', content)
        self.assertIn('$preparationMemoryBucket = [math]::Floor([math]::Max(0, $memory) / 10)', content)
        self.assertIn('$phaseProgressCheckpoints = @(25, 50, 75)', content)
        self.assertIn('$DurationSeconds * $phaseProgressCheckpoints[$phaseProgressIndex] / 100', content)
        self.assertIn('[PHASE RUNNING] $Phase ${checkpoint}% elapsed=${elapsedSeconds}s total=${DurationSeconds}s', content)
        self.assertIn('$argText = "pause:-2 skip-warnings stress -M:$targetBytes -D:60"', content)
        self.assertNotIn('-TL:$DurationSeconds"', content)

    def test_v100_windows_stress_replaces_only_the_supplemented_phase_and_disk_letters(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("function Get-SupplementPhasePattern", content)
        self.assertIn("Copy-Item -LiteralPath $baseFile.FullName -Destination $currentFile", content)
        self.assertIn("$baseKeep = @($baseRows | Where-Object { $_.Phase -notmatch $phasePattern })", content)

    def test_v100_windows_disk_supplement_renders_preserved_drives_in_html(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1").read_text(encoding="utf-8-sig")

        self.assertIn("function Get-ReportDiskDrives", content)
        self.assertIn("$reportDiskDrives = @(Get-ReportDiskDrives $diskSpd.Details)", content)
        self.assertIn("foreach($d0 in $reportDiskDrives)", content)
        self.assertIn("$diskThresholdHtml = Get-DiskThresholdSummaryHtml $reportDiskDrives", content)

    def test_v100_windows_supplement_html_rebuilds_cpu_and_gpu_from_merged_data(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1").read_text(encoding="utf-8-sig")

        self.assertIn('Stage-Row "gpu" $gpuRows', content)
        self.assertIn('Stage-Row "cpu" $cpuRows', content)
        self.assertIn('$preserveBaseTelemetry = ($Mode -ne $telemetryPhase)', content)
        self.assertIn('$baseGpuLogDir = Join-Path $script:MergeBaseReportDir "furmark_gpu_log"', content)
        self.assertIn('$gpuModuleStatus = if($hasGpuEvidence)', content)
        self.assertIn('$cpuModuleStatus = if($hasCpuEvidence)', content)
        self.assertNotIn("已保留（原报告，未补测）", content)

    def test_v100_windows_supplement_uses_merged_evidence_for_every_report_status(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1").read_text(encoding="utf-8-sig")

        self.assertIn('$hasGpuEvidence = ($gpuRows.Count -gt 0)', content)
        self.assertIn('$hasCpuEvidence = ($cpuRows.Count -gt 0)', content)
        self.assertIn('$hasDiskEvidence = ($diskRows.Count -gt 0 -or $diskSpd.Details.Count -gt 0)', content)
        self.assertIn('if($hasGpuEvidence){ $gpuEnabled = $true }', content)
        self.assertIn('if($hasCpuEvidence){ $cpuEnabled = $true }', content)
        self.assertIn('if($hasDiskEvidence){ $diskEnabled = $true }', content)
        self.assertIn('$gpuReasonDisplay = if($hasGpuEvidence){"-"}', content)
        self.assertIn('$cpuModuleReasonDisplay = if($hasCpuEvidence){"-"}', content)
        self.assertIn('$diskModuleReasonDisplay = if($hasDiskEvidence){"-"}', content)

    def test_v100_windows_supplement_uses_configured_cpu_backend_when_merged_cpu_data_exists(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1").read_text(encoding="utf-8-sig")

        self.assertIn('$effectiveCpuMemBackend = if($hasCpuEvidence -and $script:CpuMemBackendUsed -in @("NotStarted","Unknown")){ $CpuMemBackend }', content)
        self.assertIn('$backendText = if($effectiveCpuMemBackend){$effectiveCpuMemBackend}else{"Unknown"}', content)

    def test_v100_windows_disk_supplement_preserves_report_history_and_complete_tools(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1").read_text(encoding="utf-8-sig")

        self.assertIn('function Preserve-BaseDiskHistoryRows', content)
        self.assertIn('function Merge-BaseReportToolInfo', content)
        self.assertIn('$reportStartTime = Get-MinTime $rows', content)
        self.assertIn('$reportEndTime = Get-MaxTime $rows', content)
        self.assertIn('disk 原测 总计', content)
        self.assertIn('disk 补测 总计', content)
        self.assertIn('磁盘顺序读取速度（按盘）', content)
        self.assertIn('Merge-BaseReportToolInfo', content)

    def test_v100_windows_disk_trends_are_collected_and_merged_per_drive(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1").read_text(encoding="utf-8-sig")

        self.assertIn('$DiskDriveIoCsv = Join-Path $LogDir "disk_io_by_drive.csv"', content)
        self.assertIn('function Write-DiskDriveIoSamples', content)
        self.assertIn('"Timestamp,Phase,Drive,Read_MBps,Write_MBps" | Out-File $DiskDriveIoCsv', content)
        self.assertIn('Merge-BaseDiskDriveIoSamples', content)
        self.assertIn('disk_read_{0}.svg', content)
        self.assertIn('disk_write_{0}.svg', content)

    def test_v100_windows_stress_can_rebuild_html_from_existing_report_data(self) -> None:
        content = (Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1").read_text(encoding="utf-8-sig")

        self.assertIn('[string]$RebuildReportDir = ""', content)
        self.assertIn("function Restore-RebuildReportSource", content)
        self.assertIn("[REBUILD] Rebuilt report from existing data", content)
        self.assertIn("if($script:OfflineRebuildMode)", content)

    def test_v100_windows_stress_deduplicates_partitions_on_the_same_physical_disk(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn("function Resolve-PhysicalTestDrives", content)
        self.assertIn('"disk:{0}" -f $info.DiskNumber', content)
        self.assertIn("Sort-Object @{Expression={$_.IsSystemDrive};Ascending=$true}, Drive", content)
        self.assertIn("[DISK DEDUPE]", content)
        self.assertIn("$script:ResolvedTestDrives = Resolve-PhysicalTestDrives (Resolve-TestDrives)", content)

    def test_v100_windows_stress_skips_only_low_space_disks(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn("function Assert-TestDrives", content)
        self.assertIn("[DISK SKIP]", content)
        self.assertIn("$script:ResolvedTestDrives = @($eligible)", content)
        self.assertIn("No test drive has enough free space", content)
        self.assertNotIn('free space is not enough for DiskFileSize=$DiskFileSize"; exit 2', content)

    def test_v100_windows_stress_downloads_full_seven_zip_from_internal_mirror(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn(
            'http://171.221.252.54:8573/chfs/shared/%E5%85%B6%E4%BB%96%E5%B8%B8%E7%94%A8%E8%BD%AF%E4%BB%B6%EF%BC%88%E5%90%AB%E5%8E%8B%E6%B5%8B%E8%84%9A%E6%9C%AC%E7%AD%89%EF%BC%89/Stress%E5%8E%8B%E6%B5%8B%E7%9B%B8%E5%85%B3%E8%84%9A%E6%9C%AC/windows%E5%8E%8B%E6%B5%8B/7z2409-x64.exe',
            content,
        )
        self.assertNotIn("https://www.7-zip.org/a/7z2409-x64.exe", content)

    def test_v100_windows_stress_script_automatically_installs_signed_pawnio_when_elevated(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn("function Test-PawnIoSystemInstall", content)
        self.assertIn('SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\PawnIO', content)
        self.assertIn('Join-Path $env:ProgramFiles "PawnIO\\PawnIOLib.dll"', content)
        self.assertIn("if (Test-PawnIoSystemInstall) { return $true }", content)
        self.assertIn("AutoConfirmPawIoInstall", content)
        self.assertIn("PawIoConfirmTimeoutSeconds", content)
        self.assertIn("Get-AuthenticodeSignature", content)
        self.assertIn("-install -silent", content)
        self.assertIn("$exitCode -ne 0 -and $exitCode -ne 3010", content)
        self.assertIn("Test-IsAdministrator", content)
        self.assertIn("Wait-PawnIoInstallation", content)

    def test_v100_windows_report_includes_average_cpu_temperature_in_both_summaries(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn('KeyMetricRow "CPU &#x5E73;&#x5747;&#x6E29;&#x5EA6;" (FmtVal $cpuTempAvg \'C\') $cpuTempJudge', content)
        self.assertIn('MetricItem "CPU 平均温度" (FmtVal (Get-Avg $cpuRows \'CPU_Temperature_C\') \'C\')', content)

    def test_v100_windows_cpu_temperature_marks_only_values_above_95c_as_attention(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn("[int]$CpuTempWarnC = 95", content)
        self.assertIn("[int]$CpuTempFailC = 100", content)
        self.assertIn("elseif($cpuTemp -gt $CpuTempWarnC){ $extra=\"; temperature is above reference but below critical limit\" }", content)
        self.assertIn("elseif($cpuTemp -gt $CpuTempWarnC){$judgeAccept}", content)
        self.assertIn("CPU 温度 ≤ ${CpuTempWarnC} C", content)
        self.assertIn("CPU 温度 &gt; ${CpuTempWarnC} C 且 &lt; ${CpuTempFailC} C", content)

    def test_v100_windows_report_includes_average_gpu_telemetry_in_both_summaries(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn('$gpuTempAvg=Get-Avg $gpuJudgeRows "GPU_Temp_Max_C"', content)
        self.assertIn('$gpuPowerAvg=Get-Avg $gpuJudgeRows "GPU_Power_Total_W"', content)
        self.assertIn('KeyMetricRow "GPU &#x5E73;&#x5747;&#x6700;&#x9AD8;&#x6E29;&#x5EA6;" (FmtVal $gpuTempAvg \'C\') $gpuTempAvgJudge', content)
        self.assertIn('KeyMetricRow "GPU &#x5E73;&#x5747;&#x603B;&#x529F;&#x8017;" (FmtVal $gpuPowerAvg \'W\') $gpuPowerAvgJudge', content)
        self.assertIn('MetricItem "GPU 平均最高温度" (FmtVal $gpuTempAvg \'C\')', content)
        self.assertIn('MetricItem "GPU 平均总功耗" (FmtVal $gpuPowerAvg \'W\')', content)

    def test_v100_windows_report_uses_detected_power_and_thermal_limits_for_power_metrics(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn("function Get-GpuHardwareLimits", content)
        self.assertIn("--query-gpu=power.limit", content)
        self.assertIn("GPU Slowdown Temp", content)
        self.assertIn("function Select-CpuPowerLimitPercentFromSensors", content)
        self.assertIn("CPU_Power_Limit_Percent", content)
        self.assertIn("$cpuPowerLimitW=Get-CpuPowerLimitFromRows $cpuJudgeRows", content)
        self.assertIn("$gpuPowerLimitW=$script:GpuPowerLimitW", content)
        self.assertIn("$gpuThermalSlowdownC=$script:GpuThermalSlowdownC", content)
        self.assertIn("$cpuPowerAvgJudge", content)
        self.assertIn("$gpuTempAvgJudge", content)
        self.assertIn("$gpuPowerAvgJudge", content)
        self.assertNotIn('KeyMetricRow "CPU &#x6700;&#x5927;&#x529F;&#x8017;" (FmtVal $cpuPower \'W\') $judgeNote', content)
        self.assertNotIn('KeyMetricRow "GPU &#x5E73;&#x5747;&#x6700;&#x9AD8;&#x6E29;&#x5EA6;" (FmtVal $gpuTempAvg \'C\') $judgeNote', content)
        self.assertNotIn('KeyMetricRow "GPU &#x5E73;&#x5747;&#x603B;&#x529F;&#x8017;" (FmtVal $gpuPowerAvg \'W\') $judgeNote', content)

    def test_v100_windows_report_hides_unavailable_dynamic_limit_rows_from_customer_panel(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn("$dynamicThresholdInfo=@()", content)
        self.assertIn("if($cpuPowerLimitAvailable)", content)
        self.assertIn("if($gpuPowerLimitAvailable)", content)
        self.assertIn("if($gpuThermalLimitAvailable)", content)
        self.assertIn("$dynamicThresholdHtml = [string]::Join('', [string[]]$dynamicThresholdInfo)", content)
        self.assertIn("$dynamicThresholdHtml</div><div class='threshold-subtitle'>", content)
        self.assertNotIn('CPU 动态功耗上限：</b>$(Html $cpuPowerLimitText)', content)
        self.assertNotIn('GPU 动态热降频点：</b>$(Html $gpuThermalLimitText)', content)

    def test_v100_windows_report_falls_back_to_official_cpu_tdp_without_customer_facing_threshold(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v100_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn("function Get-CpuOfficialTdpW", content)
        self.assertIn('Ryzen 9 9950X' , content)
        self.assertIn("170", content)
        self.assertIn("$cpuPowerBaselineW = if($cpuPowerLimitAvailable){$cpuPowerLimitW}else{$cpuOfficialTdpW}", content)
        self.assertIn("$cpuPowerBelowBaselineJudge", content)
        self.assertIn("$cpuPowerMaxJudge", content)
        self.assertIn("$cpuPowerAvgJudge", content)
        self.assertNotIn("未识别 PPT/Power Limit，不以 TDP 猜测功耗阈值", content)

    def test_windows_powershell_script_is_saved_as_windows_category(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            backend_root = Path(temp_dir)
            scripts_root = backend_root / "scripts"
            windows_root = scripts_root / "windows"
            apptainer_root = backend_root / "apptainer"

            with patch.multiple(
                script_library,
                BACKEND_ROOT=backend_root,
                SCRIPTS_ROOT=scripts_root,
                APPTAINER_ROOT=apptainer_root,
                WINDOWS_SCRIPTS_ROOT=windows_root,
                UPLOAD_DIRECTORIES={"windows": windows_root},
                ALLOWED_SUFFIXES_BY_CATEGORY={"windows": {".ps1", ".bat", ".cmd"}},
                DISPLAY_CATEGORY_LABELS={"windows": "Windows 压测"},
            ):
                record = script_library.save_library_file("windows", "stress.ps1", b"Write-Host ok")

                self.assertEqual(record["physical_category"], "windows")
                self.assertTrue(record["previewable"])
                self.assertEqual(record["path"], "scripts/windows/stress.ps1")

    def test_windows_script_exposes_content_version_hash_and_encoding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            backend_root = Path(temp_dir)
            scripts_root = backend_root / "scripts"
            windows_root = scripts_root / "windows"

            with patch.multiple(
                script_library,
                BACKEND_ROOT=backend_root,
                SCRIPTS_ROOT=scripts_root,
                APPTAINER_ROOT=backend_root / "apptainer",
                WINDOWS_SCRIPTS_ROOT=windows_root,
                UPLOAD_DIRECTORIES={"windows": windows_root},
                ALLOWED_SUFFIXES_BY_CATEGORY={"windows": {".ps1", ".bat", ".cmd"}},
                DISPLAY_CATEGORY_LABELS={"windows": "Windows 压测"},
            ):
                record = script_library.save_library_file(
                    "windows", "v89_windows_stress.ps1", b"\xef\xbb\xbf# ScriptVersion: v89\nWrite-Host ok\n"
                )
                preview = script_library.read_library_preview(record["path"])

                self.assertEqual(record["content_version"], "v89")
                self.assertTrue(record["version_consistent"])
                self.assertEqual(len(record["sha256"]), 64)
                self.assertEqual(preview["encoding"], "utf-8-sig")

    def test_windows_script_preview_detects_utf16le(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            backend_root = Path(temp_dir)
            scripts_root = backend_root / "scripts"
            windows_root = scripts_root / "windows"

            with patch.multiple(
                script_library,
                BACKEND_ROOT=backend_root,
                SCRIPTS_ROOT=scripts_root,
                APPTAINER_ROOT=backend_root / "apptainer",
                WINDOWS_SCRIPTS_ROOT=windows_root,
                UPLOAD_DIRECTORIES={"windows": windows_root},
                ALLOWED_SUFFIXES_BY_CATEGORY={"windows": {".ps1", ".bat", ".cmd"}},
                DISPLAY_CATEGORY_LABELS={"windows": "Windows 压测"},
            ):
                record = script_library.save_library_file(
                    "windows", "v89_windows_stress.ps1", "# ScriptVersion: v89\nWrite-Host 中文\n".encode("utf-16")
                )

                preview = script_library.read_library_preview(record["path"])

                self.assertEqual(preview["encoding"], "utf-16le")
                self.assertIn("Write-Host 中文", preview["content"])

    @patch("app.core.task_runner.get_library_file_record", return_value={"physical_category": "windows"})
    def test_windows_script_is_rejected_by_linux_task_runner(self, _mock_record) -> None:
        with self.assertRaisesRegex(TaskRunnerError, "server environment scripts"):
            _resolve_task_library_file("windows/stress.ps1", "script")
