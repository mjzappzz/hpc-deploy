import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.cleanup import _group_local_artifact_batches
from app.db.database import Base
from app.models.task import Task
from app.schemas.cleanup import LocalArtifactDirectory, LocalArtifactFile


class LocalArtifactBatchFilesTests(unittest.TestCase):
    def test_batch_children_keep_their_own_files(self) -> None:
        gpu_file = LocalArtifactFile(name="gpu.xlsx", relative_path="task-gpu/gpu.xlsx")
        cpu_file = LocalArtifactFile(name="cpu.xlsx", relative_path="task-cpu/cpu.xlsx")
        directories = [
            LocalArtifactDirectory(
                name="task-gpu",
                relative_path="task-gpu",
                task_id="task-gpu",
                batch_id="batch-1",
                file_count=1,
                files=[gpu_file],
            ),
            LocalArtifactDirectory(
                name="task-cpu",
                relative_path="task-cpu",
                task_id="task-cpu",
                batch_id="batch-1",
                file_count=1,
                files=[cpu_file],
            ),
        ]

        batch = _group_local_artifact_batches(directories)[0]

        self.assertEqual([task.task_id for task in batch.child_tasks], ["task-cpu", "task-gpu"])
        files_by_task = {task.task_id: [file.name for file in task.files] for task in batch.child_tasks}
        self.assertEqual(files_by_task["task-gpu"], ["gpu.xlsx"])
        self.assertEqual(files_by_task["task-cpu"], ["cpu.xlsx"])

    def test_batch_includes_database_task_without_artifact_directory(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = sessionmaker(bind=engine)()
        try:
            session.add_all([
                Task(task_id="task-gpu", server_id=1, status="SUCCESS", batch_id="batch-1", file_name="gpu_stress_report.sh", sequence_index=0),
                Task(task_id="task-disk", server_id=1, status="CANCELED", batch_id="batch-1", file_name="disk_stress_report.sh", sequence_index=1),
            ])
            session.commit()
            directories = [LocalArtifactDirectory(
                name="task-gpu",
                relative_path="task-gpu",
                task_id="task-gpu",
                batch_id="batch-1",
                files=[LocalArtifactFile(name="gpu.xlsx", relative_path="task-gpu/gpu.xlsx")],
            )]

            batch = _group_local_artifact_batches(directories, db=session)[0]

            children = {task.task_id: task for task in batch.child_tasks}
            self.assertEqual(children["task-disk"].status, "CANCELED")
            self.assertEqual(children["task-disk"].files, [])
            self.assertEqual(children["task-disk"].file_count, 0)
        finally:
            session.close()
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
