import unittest

from app.api.tasks import _build_stress_suite_batch_ids
from app.schemas.task import StressSuiteCreateItem, StressSuiteCreateResponse


class StressSuiteBatchPartitionTests(unittest.TestCase):
    def test_each_server_receives_an_independent_batch_id(self) -> None:
        tokens = iter(("aaaaaa", "bbbbbb"))

        batch_ids = _build_stress_suite_batch_ids(
            [2, 3],
            now_str="20260730-100210",
            token_factory=lambda: next(tokens),
        )

        self.assertEqual(
            batch_ids,
            {
                2: "batch-20260730-100210-aaaaaa",
                3: "batch-20260730-100210-bbbbbb",
            },
        )

    def test_response_keeps_primary_batch_id_and_exposes_all_batches(self) -> None:
        response = StressSuiteCreateResponse(
            batch_id="batch-a",
            batch_ids=["batch-a", "batch-b"],
            batches=[
                {"server_id": 2, "server_name": "server-a", "batch_id": "batch-a"},
                {"server_id": 3, "server_name": "server-b", "batch_id": "batch-b"},
            ],
            total=2,
            items=[
                StressSuiteCreateItem(
                    server_id=2,
                    server_name="server-a",
                    batch_id="batch-a",
                    task_id="task-a",
                    script_path="scripts/stress/gpu_stress_report.sh",
                ),
                StressSuiteCreateItem(
                    server_id=3,
                    server_name="server-b",
                    batch_id="batch-b",
                    task_id="task-b",
                    script_path="scripts/stress/gpu_stress_report.sh",
                ),
            ],
        )

        self.assertEqual(response.batch_id, "batch-a")
        self.assertEqual(response.batch_ids, ["batch-a", "batch-b"])
        self.assertEqual(response.items[1].batch_id, "batch-b")


if __name__ == "__main__":
    unittest.main()
