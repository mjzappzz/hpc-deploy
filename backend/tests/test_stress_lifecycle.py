import unittest

from app.core import task_runner
from app.core.task_recovery import is_remotely_started_stress_task


class StressLifecycleTests(unittest.TestCase):
    def test_preparation_timeout_is_independent_from_stress_duration(self) -> None:
        self.assertGreater(task_runner.STRESS_PREPARATION_TIMEOUT_SECONDS, 300)
        self.assertEqual(
            task_runner.stress_poll_deadline_seconds(duration_seconds=180, stress_started=False),
            task_runner.STRESS_PREPARATION_TIMEOUT_SECONDS,
        )

    def test_stress_duration_deadline_starts_after_stress_start_marker(self) -> None:
        self.assertFalse(task_runner.stress_started_in_log('[STAGE] dependency_check_done'))
        self.assertTrue(task_runner.stress_started_in_log('[STAGE] stress_start'))
        self.assertEqual(
            task_runner.stress_poll_deadline_seconds(duration_seconds=180, stress_started=True),
            180 + task_runner._calculate_stress_grace(180),
        )

    def test_healthy_running_stress_does_not_fail_after_runtime_estimate(self) -> None:
        self.assertFalse(
            task_runner.stress_elapsed_requires_failure(
                duration_seconds=180,
                stress_started=True,
                elapsed_seconds=180 + task_runner._calculate_stress_grace(180),
            )
        )

    def test_unstarted_stress_still_fails_after_preparation_limit(self) -> None:
        self.assertTrue(
            task_runner.stress_elapsed_requires_failure(
                duration_seconds=180,
                stress_started=False,
                elapsed_seconds=task_runner.STRESS_PREPARATION_TIMEOUT_SECONDS,
            )
        )

    def test_remotely_started_preparing_stress_task_is_not_requeued_after_restart(self) -> None:
        self.assertTrue(is_remotely_started_stress_task({"stress_remote_started": True}))
        self.assertFalse(is_remotely_started_stress_task({}))


if __name__ == '__main__':
    unittest.main()
