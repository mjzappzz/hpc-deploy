import unittest

from app.core.task_diagnosis import diagnose_task_failure


class TaskDiagnosisTests(unittest.TestCase):
    def test_gpu_startup_marker_mismatch_is_attributed_to_platform(self) -> None:
        diagnosis = diagnose_task_failure(
            task_status="FAILED",
            error_message="stress failed before start: dependency installation did not finish within 300s",
            logs=[
                "[INFO] Missing dependencies detected, installing...",
                "[INFO] gpu-burn build success: /opt/software/gpu-burn/gpu_burn",
                "[INFO] Start gpu-burn (FP64). It will stress all visible NVIDIA GPUs.",
                "stress async: startup stalled: stress failed before start: dependency installation did not finish within 300s",
            ],
            task_type="stress",
            file_name="gpu_stress_report.sh",
        )

        self.assertEqual(diagnosis["category"], "stress_startup_marker_mismatch")
        self.assertEqual(diagnosis["attribution"], "platform")
        self.assertIn("旧版脚本缺少启动阶段标记", diagnosis["conclusion"])

    def test_stress_root_requirement_has_specific_diagnosis(self) -> None:
        diagnosis = diagnose_task_failure(
            task_status="FAILED",
            error_message="stress failed before start: root user is required",
            logs=["[ERROR] 请使用 root 用户运行，或使用 sudo"],
            task_type="stress",
            file_name="cpu_mem_stress_report.sh",
        )

        self.assertEqual(diagnosis["category"], "stress_root_required")
        self.assertIn("root", diagnosis["conclusion"])
        self.assertTrue(any("SSH 用户" in item for item in diagnosis["possible_causes"]))

    def test_stress_ssh_degraded_is_not_classified_as_apptainer_failure(self) -> None:
        diagnosis = diagnose_task_failure(
            task_status="FAILED",
            error_message="stress async: poll loop crashed at 5010s: SSH degraded after 3 consecutive failures",
            logs=[
                "stress async: SSH failed 3x consecutively, forcing executor refresh",
                "stress async: poll loop crashed at 5010s: SSH degraded after 3 consecutive failures",
                "stress async: fresh SSH connection also failed, giving up",
            ],
            task_type="stress",
            file_name="cpu_mem_stress_report.sh",
        )

        self.assertEqual(diagnosis["category"], "ssh_connection_failed")
        self.assertNotEqual(diagnosis["category"], "apptainer_upload_failed")

    def test_apptainer_upload_failure_remains_classified_for_apptainer_task(self) -> None:
        diagnosis = diagnose_task_failure(
            task_status="FAILED",
            error_message="SFTP upload failed: remote file already exists",
            logs=["SFTP upload failed: remote file already exists"],
            task_type="apptainer",
            file_name="image.sif",
        )

        self.assertEqual(diagnosis["category"], "apptainer_upload_failed")

    def test_recovery_ssh_error_is_not_misclassified_as_gpu_failure(self) -> None:
        diagnosis = diagnose_task_failure(
            task_status="FAILED",
            error_message="recovery: SSH connect failed: SSH network error: [Errno 1] Operation not permitted",
            logs=[
                "[INFO] nvidia-smi path: /usr/bin/nvidia-smi",
                "[INFO] CUDA Toolkit Version: 12.8.61",
                "[INFO] Start gpu-burn.",
                "recovery: SSH connect failed: SSH network error: [Errno 1] Operation not permitted",
            ],
            task_type="stress",
            file_name="gpu_stress_report.sh",
        )

        self.assertEqual(diagnosis["category"], "ssh_connection_failed")


if __name__ == "__main__":
    unittest.main()
