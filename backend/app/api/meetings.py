from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.models.meeting import MeetingStatus, MeetingType
from app.schemas.meeting import (
    MeetingCreate,
    MeetingListResponse,
    MeetingResponse,
    MeetingUpdate,
)
from app.services.file_service import file_service
from app.services.meeting_service import meeting_service
from app.api.transcription import transcribe_meeting


router = APIRouter(
    prefix="/meetings",
    tags=["Meetings"],
)


def _process_meeting_in_background(meeting_id: UUID) -> None:
    """Transcribe and analyze a meeting using a dedicated database session."""
    db = SessionLocal()

    try:
        meeting = meeting_service.get_meeting(db, meeting_id)

        if meeting is None or not meeting.file_path:
            return

        # Step 1: Transcribe audio and identify speakers.
        transcribe_meeting(meeting_id, db)

        db.expire_all()
        meeting = meeting_service.get_meeting(db, meeting_id)

        if meeting is None:
            return

        # Stop if transcription explicitly failed.
        if meeting.status == MeetingStatus.FAILED:
            return

        # Transcription must have saved its completed stage.
        if meeting.processing_stage != "transcription_completed":
            raise RuntimeError(
                "Transcription did not reach the transcription_completed stage."
            )

        # Step 2: Run AI analysis on the saved transcript.
        meeting.processing_stage = "analyzing"
        meeting.status = MeetingStatus.PROCESSING
        db.commit()

        from app.services.analysis_service import analysis_service

        asyncio.run(
            analysis_service.analyze_meeting(
                db=db,
                meeting_id=meeting_id,
            )
        )

        # Step 3: Mark the complete workflow as finished.
        db.expire_all()
        meeting = meeting_service.get_meeting(db, meeting_id)

        if meeting is not None:
            meeting.status = MeetingStatus.COMPLETED
            meeting.processing_stage = "completed"
            db.commit()

        print(f"[Background Processing] Meeting {meeting_id} completed.")

    except Exception as exc:
        db.rollback()

        print(
            f"[Background Processing] Meeting {meeting_id} failed: "
            f"{type(exc).__name__}: {exc}"
        )

        try:
            meeting = meeting_service.get_meeting(db, meeting_id)

            if meeting is not None:
                meeting.status = MeetingStatus.FAILED
                meeting.processing_stage = "failed"
                db.commit()

        except Exception:
            db.rollback()

    finally:
        db.close()


@router.post(
    "",
    response_model=MeetingResponse,
)
async def create_meeting(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    description: str | None = Form(None),
    meeting_type: MeetingType = Form(MeetingType.BUSINESS),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    """Create a meeting and schedule processing when a file is provided."""

    data = MeetingCreate(
        title=title,
        description=description,
        meeting_type=meeting_type,
    )

    try:
        meeting = meeting_service.create_meeting(db, data)

        if file is not None:
            file_path, original_filename = await file_service.save_file(file)

            meeting = meeting_service.attach_file(
                db=db,
                meeting=meeting,
                file_path=file_path,
                original_filename=original_filename,
            )

            meeting.status = MeetingStatus.PROCESSING
            meeting.processing_stage = "queued"
            db.commit()
            db.refresh(meeting)

            background_tasks.add_task(
                _process_meeting_in_background,
                meeting.id,
            )

        return meeting

    except HTTPException:
        raise

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create meeting: {exc}",
        ) from exc


@router.get(
    "",
    response_model=MeetingListResponse,
)
def list_meetings(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: MeetingStatus | None = None,
    meeting_type: MeetingType | None = None,
    db: Session = Depends(get_db),
):
    meetings, total, total_pages = meeting_service.list_meetings(
        db=db,
        page=page,
        page_size=page_size,
        status=status,
        meeting_type=meeting_type,
    )

    return MeetingListResponse(
        items=meetings,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/{meeting_id}/status")
def get_meeting_processing_status(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):
    meeting = meeting_service.get_meeting(db, meeting_id)

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    return {
        "meeting_id": str(meeting.id),
        "status": meeting.status.value,
        "processing_stage": meeting.processing_stage,
        "duration_seconds": meeting.duration_seconds,
    }


@router.get(
    "/{meeting_id}",
    response_model=MeetingResponse,
)
def get_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):
    meeting = meeting_service.get_meeting(db, meeting_id)

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    return meeting


@router.patch(
    "/{meeting_id}",
    response_model=MeetingResponse,
)
def update_meeting(
    meeting_id: UUID,
    data: MeetingUpdate,
    db: Session = Depends(get_db),
):
    meeting = meeting_service.get_meeting(db, meeting_id)

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    return meeting_service.update_meeting(db, meeting, data)


@router.post(
    "/{meeting_id}/upload",
    response_model=MeetingResponse,
)
async def upload_meeting_file(
    meeting_id: UUID,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    meeting = meeting_service.get_meeting(db, meeting_id)

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    try:
        file_path, original_filename = await file_service.save_file(file)

        meeting = meeting_service.attach_file(
            db=db,
            meeting=meeting,
            file_path=file_path,
            original_filename=original_filename,
        )

        meeting.status = MeetingStatus.PROCESSING
        meeting.processing_stage = "queued"
        db.commit()
        db.refresh(meeting)

        background_tasks.add_task(
            _process_meeting_in_background,
            meeting.id,
        )

        return meeting

    except HTTPException:
        raise

    except ValueError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload meeting file: {exc}",
        ) from exc


@router.delete("/{meeting_id}")
def delete_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):
    meeting = meeting_service.get_meeting(db, meeting_id)

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    try:
        meeting_service.delete_meeting(db, meeting)
        return {"message": "Meeting deleted successfully."}

    except HTTPException:
        raise

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete meeting: {exc}",
        ) from exc