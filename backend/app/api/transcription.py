from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.meeting import Meeting, MeetingStatus
from app.models.transcript import TranscriptSegment
from app.schemas.transcript import TranscriptResponse
from app.services.diarization_service import diarization_service
from app.services.transcription_service import transcription_service


router = APIRouter(
    prefix="/transcription",
    tags=["Transcription"],
)


def update_processing_stage(
    db: Session,
    meeting: Meeting,
    stage: str,
) -> None:
    """Save the current processing stage for frontend polling."""
    meeting.processing_stage = stage
    db.commit()

    print(
        f"[Processing] Meeting {meeting.id}: {stage}"
    )


@router.post(
    "/{meeting_id}",
    response_model=TranscriptResponse,
)
def transcribe_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):
    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id
        )
    )

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    if not meeting.file_path:
        raise HTTPException(
            status_code=400,
            detail="No media file uploaded for this meeting.",
        )

    try:
        # Overall processing remains active until AI analysis finishes.
        meeting.status = MeetingStatus.PROCESSING
        update_processing_stage(
            db,
            meeting,
            "transcribing",
        )

        # 1. Convert audio into transcript segments.
        transcription = transcription_service.transcribe(
            meeting.file_path
        )

        transcript_segments = transcription["segments"]

        # 2. Identify speakers.
        update_processing_stage(
            db,
            meeting,
            "identifying_speakers",
        )

        diarization_status = "not_available"

        try:
            speaker_segments = diarization_service.diarize(
                meeting.file_path
            )

            transcript_segments = (
                diarization_service.attach_speakers(
                    transcript_segments,
                    speaker_segments,
                )
            )

            labeled_count = sum(
                1
                for segment in transcript_segments
                if segment.get("speaker_label")
            )

            diarization_status = (
                "completed"
                if labeled_count > 0
                else "completed_no_matches"
            )

            print(
                f"[Diarization] Status: {diarization_status}; "
                f"speaker segments: {len(speaker_segments)}; "
                f"transcript segments: {len(transcript_segments)}; "
                f"labeled segments: {labeled_count}"
            )

        except Exception as exc:
            # Speaker detection is optional; preserve the transcript.
            diarization_status = "failed"

            print(
                f"[Diarization] Failed: "
                f"{type(exc).__name__}: {exc}"
            )

        # 3. Save the transcript.
        update_processing_stage(
            db,
            meeting,
            "saving_transcript",
        )

        db.execute(
            delete(TranscriptSegment).where(
                TranscriptSegment.meeting_id == meeting_id
            )
        )

        for segment in transcript_segments:
            db.add(
                TranscriptSegment(
                    meeting_id=meeting_id,
                    speaker_label=segment.get("speaker_label"),
                    speaker_name=segment.get("speaker_name"),
                    text=segment["text"],
                    start_time=float(segment["start_time"]),
                    end_time=float(segment["end_time"]),
                    sequence_number=int(
                        segment["sequence_number"]
                    ),
                )
            )

        # 4. Save duration, but do not mark the whole meeting complete.
        duration = transcription.get("duration")

        if duration is None and transcript_segments:
            duration = max(
                float(segment["end_time"])
                for segment in transcript_segments
            )

        meeting.duration_seconds = (
            round(duration)
            if duration is not None
            else None
        )

        meeting.status = MeetingStatus.PROCESSING
        meeting.processing_stage = "transcription_completed"

        db.commit()

        # 5. Read back the persisted transcript.
        saved_segments = list(
            db.scalars(
                select(TranscriptSegment)
                .where(
                    TranscriptSegment.meeting_id == meeting_id
                )
                .order_by(
                    TranscriptSegment.sequence_number
                )
            ).all()
        )

        print(
            f"[Transcription] Completed for meeting {meeting_id}; "
            f"segments={len(saved_segments)}; "
            f"diarization={diarization_status}"
        )

        return TranscriptResponse(
            meeting_id=meeting_id,
            segments=saved_segments,
            total_segments=len(saved_segments),
            duration_seconds=(
                float(meeting.duration_seconds)
                if meeting.duration_seconds is not None
                else None
            ),
        )

    except FileNotFoundError as exc:
        db.rollback()

        try:
            meeting.status = MeetingStatus.FAILED
            meeting.processing_stage = "failed"
            db.commit()
        except Exception:
            db.rollback()

        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        db.rollback()

        try:
            meeting.status = MeetingStatus.FAILED
            meeting.processing_stage = "failed"
            db.commit()
        except Exception:
            db.rollback()

        print(
            f"[Transcription] Failed: "
            f"{type(exc).__name__}: {exc}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Transcription failed: {str(exc)}",
        ) from exc


@router.get(
    "/{meeting_id}",
    response_model=TranscriptResponse,
)
def get_transcript(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):
    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id
        )
    )

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    segments = list(
        db.scalars(
            select(TranscriptSegment)
            .where(
                TranscriptSegment.meeting_id == meeting_id
            )
            .order_by(
                TranscriptSegment.sequence_number
            )
        ).all()
    )

    duration = (
        max(
            float(segment.end_time)
            for segment in segments
        )
        if segments
        else None
    )

    return TranscriptResponse(
        meeting_id=meeting_id,
        segments=segments,
        total_segments=len(segments),
        duration_seconds=duration,
    )