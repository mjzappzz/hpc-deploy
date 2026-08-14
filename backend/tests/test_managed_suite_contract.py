from types import SimpleNamespace
import unittest

from app.api.tasks import MANAGED_SUITE_ACTIONS, _build_managed_suite_batch_ids, _managed_suite_effective_tasks
from app.schemas.task import ManagedSuiteCreateRequest


class ManagedSuiteContractTests(unittest.TestCase):
    def test_each_server_gets_an_independent_batch(self) -> None:
        tokens = iter(["server-a", "server-b"])

        batch_ids = _build_managed_suite_batch_ids(
            [101, 202],
            now_str="20260730-180000",
            token_factory=lambda: next(tokens),
        )

        self.assertEqual(
            batch_ids,
            {
                101: "batch-20260730-180000-server-a",
                202: "batch-20260730-180000-server-b",
            },
        )

    def test_base_system_order_is_fixed(self) -> None:
        self.assertEqual(
            [action for action, _path in MANAGED_SUITE_ACTIONS["base_system"]],
            ["disable_lock_sleep", "lock_release"],
        )

    def test_gpu_install_order_is_fixed(self) -> None:
        request = ManagedSuiteCreateRequest(
            suite_type="gpu_software",
            server_ids=[1, 2],
            actions=["gpu_driver", "cuda_toolkit"],
            driver_type="datacenter",
            driver_id="a" * 24,
        )

        self.assertEqual(request.actions, ["gpu_driver", "cuda_toolkit"])
        self.assertEqual(
            [action for action, _path in MANAGED_SUITE_ACTIONS["gpu_software"]],
            request.actions,
        )

    def test_managed_suite_retry_replaces_the_failed_step_for_scheduling(self) -> None:
        tasks = [
            SimpleNamespace(id=1, task_id="task-first", sequence_index=1, params={}, status="SUCCESS"),
            SimpleNamespace(id=2, task_id="task-failed", sequence_index=2, params={}, status="FAILED"),
            SimpleNamespace(
                id=3, task_id="task-retry", sequence_index=3,
                params={"__retry_of_task_id": "task-failed"}, status="PENDING",
            ),
        ]

        effective = _managed_suite_effective_tasks(tasks)

        self.assertEqual([task.task_id for task in effective], ["task-first", "task-retry"])


if __name__ == "__main__":
    unittest.main()
