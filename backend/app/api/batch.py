from pathlib import Path
from urllib.parse import quote

from app.core.batch_report_exporter import export_batch_report_zip
from app.db.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

router = APIRouter(prefix="/batch", tags=["batch"])


def _iter_file(path: Path):
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            yield chunk


def _cleanup_file(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


@router.get("/{batch_id}/report/download-zip")
def download_batch_report_zip(batch_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    exported = export_batch_report_zip(db, batch_id)
    if exported is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="batch not found")

    encoded_name = quote(exported.filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
    }
    return StreamingResponse(
        _iter_file(exported.path),
        media_type="application/zip",
        headers=headers,
        background=BackgroundTask(_cleanup_file, exported.path),
    )
