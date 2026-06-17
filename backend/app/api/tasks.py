from app.db.database import get_db
from app.models.task import Task
from app.models.task_log import TaskLog
from app.schemas.log import TaskLogRead
from app.schemas.task import TaskRead
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _get_task_or_404(db: Session, task_id: str) -> Task:
    task = db.query(Task).filter(Task.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="task not found")
    return task


@router.get("", response_model=list[TaskRead])
def list_tasks(db: Session = Depends(get_db)) -> list[Task]:
    return db.query(Task).order_by(Task.id.desc()).all()


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: str, db: Session = Depends(get_db)) -> Task:
    return _get_task_or_404(db, task_id)


@router.get("/{task_id}/logs", response_model=list[TaskLogRead])
def list_task_logs(task_id: str, db: Session = Depends(get_db)) -> list[TaskLog]:
    _get_task_or_404(db, task_id)
    return (
        db.query(TaskLog)
        .filter(TaskLog.task_id == task_id)
        .order_by(TaskLog.id.asc())
        .all()
    )

