import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import script_library
from app.core.task_runner import TaskRunnerError, _resolve_task_library_file


class WindowsScriptLibraryTests(unittest.TestCase):
    def test_v97_windows_stress_script_automatically_installs_signed_pawnio_when_elevated(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v97_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn("AutoConfirmPawIoInstall", content)
        self.assertIn("PawIoConfirmTimeoutSeconds", content)
        self.assertIn("Get-AuthenticodeSignature", content)
        self.assertIn("-install -silent", content)
        self.assertIn("$exitCode -ne 0 -and $exitCode -ne 3010", content)
        self.assertIn("Test-IsAdministrator", content)
        self.assertIn("Wait-PawnIoInstallation", content)

    def test_v97_windows_report_includes_average_cpu_temperature_in_both_summaries(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v97_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn('KeyMetricRow "CPU &#x5E73;&#x5747;&#x6E29;&#x5EA6;" (FmtVal $cpuTempAvg \'C\') $cpuTempJudge', content)
        self.assertIn('MetricItem "CPU 平均温度" (FmtVal (Get-Avg $cpuRows \'CPU_Temperature_C\') \'C\')', content)

    def test_v97_windows_report_includes_average_gpu_telemetry_in_both_summaries(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v97_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn('$gpuTempAvg=Get-Avg $gpuJudgeRows "GPU_Temp_Max_C"', content)
        self.assertIn('$gpuPowerAvg=Get-Avg $gpuJudgeRows "GPU_Power_Total_W"', content)
        self.assertIn('KeyMetricRow "GPU &#x5E73;&#x5747;&#x6700;&#x9AD8;&#x6E29;&#x5EA6;" (FmtVal $gpuTempAvg \'C\') $gpuTempAvgJudge', content)
        self.assertIn('KeyMetricRow "GPU &#x5E73;&#x5747;&#x603B;&#x529F;&#x8017;" (FmtVal $gpuPowerAvg \'W\') $gpuPowerAvgJudge', content)
        self.assertIn('MetricItem "GPU 平均最高温度" (FmtVal $gpuTempAvg \'C\')', content)
        self.assertIn('MetricItem "GPU 平均总功耗" (FmtVal $gpuPowerAvg \'W\')', content)

    def test_v97_windows_report_uses_detected_power_and_thermal_limits_for_power_metrics(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v97_windows_stress.ps1"
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

    def test_v97_windows_report_hides_unavailable_dynamic_limit_rows_from_customer_panel(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v97_windows_stress.ps1"
        content = script_path.read_text(encoding="utf-8-sig")

        self.assertIn("$dynamicThresholdInfo=@()", content)
        self.assertIn("if($cpuPowerLimitAvailable)", content)
        self.assertIn("if($gpuPowerLimitAvailable)", content)
        self.assertIn("if($gpuThermalLimitAvailable)", content)
        self.assertIn("$dynamicThresholdHtml = [string]::Join('', [string[]]$dynamicThresholdInfo)", content)
        self.assertIn("$dynamicThresholdHtml</div><div class='threshold-subtitle'>", content)
        self.assertNotIn('CPU 动态功耗上限：</b>$(Html $cpuPowerLimitText)', content)
        self.assertNotIn('GPU 动态热降频点：</b>$(Html $gpuThermalLimitText)', content)

    def test_v97_windows_report_falls_back_to_official_cpu_tdp_without_customer_facing_threshold(self) -> None:
        script_path = Path(__file__).resolve().parents[1] / "scripts" / "windows" / "v97_windows_stress.ps1"
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
