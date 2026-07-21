import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.core import script_library
from app.core.task_runner import TaskRunnerError, _resolve_task_library_file


class WindowsScriptLibraryTests(unittest.TestCase):
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
