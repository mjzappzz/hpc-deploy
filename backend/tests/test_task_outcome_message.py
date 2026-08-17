import unittest

from app.core.task_serializer import (
    normalize_success_skip_message,
    resolve_card_outcome_title,
    resolve_success_outcome_message,
)


class TaskOutcomeMessageTests(unittest.TestCase):
    def test_normalizes_supported_whole_task_skip_messages(self) -> None:
        self.assertEqual(
            normalize_success_skip_message("[INFO] 当前系统版本为 Rocky Linux 9.8，非 9.4，无需锁定系统版本"),
            "当前系统版本为 Rocky Linux 9.8，非 9.4，无需锁定系统版本",
        )
        self.assertEqual(
            normalize_success_skip_message("nvidia-smi is available; skipping NVIDIA driver installation"),
            "检测到 nvidia-smi 可用，已跳过 NVIDIA 驱动安装",
        )
        self.assertEqual(
            normalize_success_skip_message("CUDA Toolkit 12.8 is already installed; skipping"),
            "CUDA Toolkit 12.8 已安装，已跳过安装",
        )

    def test_ignores_partial_step_skip_messages(self) -> None:
        self.assertIsNone(normalize_success_skip_message("Dependencies already installed, skip install."))
        self.assertIsNone(normalize_success_skip_message("Nouveau is not loaded; skipping disable/reboot and continuing installation"))

    def test_reports_oneapi_when_all_target_components_were_already_installed(self) -> None:
        self.assertEqual(
            resolve_success_outcome_message(
                "install_oneapi_2022.sh",
                [
                    "[INFO] BaseKit 目标组件已安装，跳过安装",
                    "[INFO] HPCKit 目标组件已安装，跳过安装",
                ],
            ),
            "Intel oneAPI 2022 目标组件原已安装，本次未重复安装，仅完成验证",
        )

    def test_does_not_report_oneapi_for_a_partial_component_skip(self) -> None:
        self.assertIsNone(
            resolve_success_outcome_message(
                "install_oneapi_2022.sh",
                ["[INFO] BaseKit 目标组件已安装，跳过安装"],
            )
        )

    def test_reports_aocc_stack_when_all_target_components_were_already_installed(self) -> None:
        self.assertEqual(
            resolve_success_outcome_message(
                "install_openmpi_4.1.6_aocc_aocl.sh",
                [
                    "[INFO] AOCC 已安装，跳过安装",
                    "[INFO] AOCL 已安装，跳过安装",
                    "[INFO] OpenMPI 4.1.6 已安装，跳过编译：/opt/openmpi/4.1.6",
                ],
            ),
            "AOCC、AOCL、OpenMPI 4.1.6 原已安装，本次未重复安装，仅完成验证",
        )

    def test_does_not_report_aocc_stack_for_partial_component_skips(self) -> None:
        self.assertIsNone(
            resolve_success_outcome_message(
                "install_openmpi_4.1.6_aocc_aocl.sh",
                [
                    "[INFO] AOCC 已安装，跳过安装",
                    "[INFO] AOCL 已安装，跳过安装",
                ],
            )
        )

    def test_uses_specific_diagnosis_title_before_report_failure_fallback(self) -> None:
        self.assertEqual(
            resolve_card_outcome_title(
                task_type="stress",
                report_status="UNKNOWN",
                diagnosis={"title": "GPU 压测日志 OOM 且混合架构未全覆盖"},
                fallback="完整失败原因",
            ),
            "GPU 压测日志 OOM 且混合架构未全覆盖",
        )
        self.assertEqual(
            resolve_card_outcome_title(
                task_type="stress",
                report_status="FAIL",
                diagnosis={"title": "GPU 内核镜像无法加载"},
                fallback="完整失败原因",
            ),
            "GPU 内核镜像无法加载",
        )

    def test_report_failure_title_uses_the_actual_stress_script_module(self) -> None:
        self.assertEqual(
            resolve_card_outcome_title(
                task_type="stress",
                file_name="cpu_mem_stress_report.sh",
                report_status="FAIL",
                diagnosis={"title": "任务执行成功"},
                fallback="报告失败原因",
            ),
            "CPU/内存压测报告未通过",
        )
        self.assertEqual(
            resolve_card_outcome_title(
                task_type="stress",
                file_name="gpu_stress_report.sh",
                report_status="FAIL",
                diagnosis=None,
                fallback="报告失败原因",
            ),
            "GPU 压测报告未通过",
        )

    def test_cpu_memory_card_title_uses_verified_ecc_failure_reason(self) -> None:
        self.assertEqual(
            resolve_card_outcome_title(
                task_type="stress",
                file_name="cpu_mem_stress_report.sh",
                report_status="FAIL",
                diagnosis={"title": "任务执行成功"},
                fallback="检测到可纠正 ECC 内存错误（MCE/CECC）；系统已纠正，但反复出现表示内存子系统存在风险。",
            ),
            "检测到可纠正 ECC 内存错误（MCE/CECC）",
        )

    def test_report_failure_card_preserves_the_actual_report_reason_for_gpu_and_disk(self) -> None:
        self.assertEqual(
            resolve_card_outcome_title(
                task_type="stress",
                file_name="gpu_stress_report.sh",
                report_status="FAIL",
                diagnosis={"title": "任务执行成功"},
                fallback="GPU 2 温度超过安全阈值，已触发保护。请检查散热。",
            ),
            "GPU 2 温度超过安全阈值，已触发保护",
        )
        self.assertEqual(
            resolve_card_outcome_title(
                task_type="stress",
                file_name="disk_stress_report.sh",
                report_status="FAIL",
                diagnosis=None,
                fallback="Disk I/O error detected on /data.",
            ),
            "Disk I/O error detected on /data",
        )


if __name__ == "__main__":
    unittest.main()
