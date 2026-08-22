import unittest

from app.core.report_summary import extract_report_failure_reason, resolve_failure_reason


class ReportSummaryFailureReasonTests(unittest.TestCase):
    def test_extracts_the_actual_failure_reason_from_each_stress_report_format(self) -> None:
        self.assertEqual(
            extract_report_failure_reason("测试结果              : FAIL\n判定原因              : GPU 2 温度超过安全阈值。"),
            "GPU 2 温度超过安全阈值。",
        )
        self.assertEqual(
            extract_report_failure_reason("Result : FAIL\nReason : Disk I/O error detected on /data."),
            "Disk I/O error detected on /data.",
        )

    def test_successful_task_without_report_has_no_failure_reason(self) -> None:
        self.assertIsNone(
            resolve_failure_reason(
                None,
                "UNKNOWN",
                {
                    "category": "completed",
                    "conclusion": "任务已成功完成。",
                },
            )
        )

    def test_shell_unbound_variable_uses_verified_conclusion(self) -> None:
        diagnosis = {
            "category": "shell_unbound_variable",
            "conclusion": "GPU 压测脚本引用了未初始化变量 build_dir，脚本在启动负载后立即退出，未生成报告。",
        }

        self.assertEqual(
            resolve_failure_reason(
                "stress script exited before report generation, no report found",
                "UNKNOWN",
                diagnosis,
            ),
            diagnosis["conclusion"],
        )

    def test_platform_marker_mismatch_uses_structured_conclusion(self) -> None:
        diagnosis = {
            "category": "stress_startup_marker_mismatch",
            "conclusion": "GPU 压测已实际启动，但旧版脚本缺少启动阶段标记，平台误判并终止任务。",
        }

        self.assertEqual(
            resolve_failure_reason(
                "stress failed before start: dependency installation did not finish within 300s",
                "UNKNOWN",
                diagnosis,
            ),
            diagnosis["conclusion"],
        )

    def test_stress_preflight_error_message_is_shown_when_diagnosis_has_no_allowlisted_category(self) -> None:
        self.assertEqual(
            resolve_failure_reason(
                "GPU stress failed before start: nvidia-smi not found",
                "UNKNOWN",
                {
                    "category": "stress_preflight_failed",
                    "conclusion": "GPU stress failed before start: nvidia-smi not found",
                },
            ),
            "GPU stress failed before start: nvidia-smi not found",
        )

    def test_interrupted_stress_without_evidence_uses_conservative_fallback(self) -> None:
        diagnosis = {
            "category": "stress_interrupted_before_report",
            "conclusion": "压测已进入实际负载后异常中断，疑似服务器重启或异常中断。",
        }

        self.assertEqual(
            resolve_failure_reason(
                "stress script exited before report generation, no report found",
                "UNKNOWN",
                diagnosis,
            ),
            "任务执行失败，未能从已回收日志确认具体根因，请查看任务日志与结果文件。",
        )

    def test_uncorrected_memory_error_uses_structured_conclusion(self) -> None:
        diagnosis = {
            "category": "uncorrected_memory_hardware_error",
            "conclusion": "内核日志已检测到不可纠正内存硬件错误。",
        }

        self.assertEqual(
            resolve_failure_reason(
                "stress script exited before report generation, no report found",
                "UNKNOWN",
                diagnosis,
            ),
            diagnosis["conclusion"],
        )

    def test_gpu_kernel_image_error_uses_verified_conclusion(self) -> None:
        diagnosis = {
            "category": "gpu_kernel_image_unavailable",
            "conclusion": "日志显示 no kernel image，目标 GPU 未启动负载。",
        }
        self.assertEqual(
            resolve_failure_reason("报告已生成，压测结果为 FAIL", "FAIL", diagnosis),
            diagnosis["conclusion"],
        )

    def test_explicit_report_reason_takes_priority_over_a_different_platform_rule(self) -> None:
        self.assertEqual(
            resolve_failure_reason(
                "报告已生成，压测结果为 FAIL",
                "FAIL",
                {
                    "category": "gpu_kernel_image_unavailable",
                    "conclusion": "日志显示 no kernel image，目标 GPU 未启动负载。",
                },
                log_messages=["Reason : GPU 2 temperature exceeded the safety threshold."],
            ),
            "GPU 2 temperature exceeded the safety threshold.",
        )

    def test_gpu_burn_source_missing_uses_structured_conclusion(self) -> None:
        diagnosis = {
            "category": "gpu_burn_source_missing",
            "conclusion": "压测启动前未找到服务器上的 gpu-burn 源码，且自动恢复下载未完成，因此未开始 GPU 压测。",
        }
        self.assertEqual(
            resolve_failure_reason("gpu-burn source recovery failed", "UNKNOWN", diagnosis),
            diagnosis["conclusion"],
        )

    def test_package_manager_lock_uses_structured_conclusion(self) -> None:
        diagnosis = {
            "category": "package_manager_locked",
            "conclusion": "apt/dpkg 正被其他进程占用，任务无法继续执行。",
        }
        self.assertEqual(
            resolve_failure_reason("command exited with code 100", "UNKNOWN", diagnosis),
            diagnosis["conclusion"],
        )

    def test_report_failure_without_verified_root_cause_is_conservative(self) -> None:
        self.assertEqual(
            resolve_failure_reason("报告已生成，压测结果为 FAIL", "FAIL", {"category": "completed"}),
            "压测未通过，未能从已回收日志确认具体根因，请查看任务日志与结果文件。",
        )

    def test_report_failure_uses_reason_from_collected_log(self) -> None:
        self.assertEqual(
            resolve_failure_reason(
                "报告已生成，压测结果为 FAIL",
                "FAIL",
                {"category": "completed"},
                log_messages=[
                    "Result       : FAIL",
                    "Reason       : Critical kernel error detected.",
                ],
            ),
            "压测未通过，未能从已回收日志确认具体根因，请查看任务日志与结果文件。",
        )

    def test_cpu_memory_report_reclassifies_corrected_ecc_mce_from_artifact_evidence(self) -> None:
        self.assertEqual(
            resolve_failure_reason(
                "报告已生成，压测结果为 FAIL",
                "FAIL",
                {"category": "completed"},
                file_name="cpu_mem_stress_report.sh",
                log_messages=[
                    "Reason       : Critical kernel error detected.",
                    "mce: [Hardware Error]: Machine check events logged",
                    "[Hardware Error]: Corrected error, no action required.",
                    "[Hardware Error]: CPU:66 MC18_STATUS[Over|CE|MiscV|AddrV|-|-|SyndV|CECC|-|-|-]",
                ],
            ),
            "检测到可纠正 ECC 内存错误（MCE/CECC）；系统已纠正，但反复出现表示内存子系统存在风险。请检查 DIMM、内存通道、CPU 内存控制器、主板与固件。",
        )


if __name__ == "__main__":
    unittest.main()
