from __future__ import annotations

import asyncio
import re
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.database import SessionLocal, get_db
from app.models.meeting import MeetingStatus, MeetingType
from app.models.transcript import TranscriptSegment
from app.schemas.meeting import MeetingCreate, MeetingResponse
from app.services.meeting_service import meeting_service

router = APIRouter(prefix="/meetings", tags=["Transcript Upload"])

MAX_BYTES = 2 * 1024 * 1024

LINE_PATTERN = re.compile(
    r"^(?:\[(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\]\s*)?"
    r"(?P<speaker>[^:\n]{1,100}):\s*(?P<text>.+)$"
)


def parse_time(value: str | None) -> float:
    if not value:
        return 0.0

    parts = [int(part) for part in value.split(":")]

    if len(parts) == 2:
        return float(parts[0] * 60 + parts[1])

    return float(parts[0] * 3600 + parts[1] * 60 + parts[2])


def parse_transcript(content: str) -> list[dict]:
    segments = []

    for line in content.splitlines():
        line = line.strip()

        if not line:
            continue

        match = LINE_PATTERN.match(line)

        if match:
            speaker = match.group("speaker").strip()
            text = match.group("text").strip()
            start = parse_time(match.group("time"))
        else:
            speaker = None
            text = line
            start = 0.0

        if not text:
            continue

        segments.append({
            "speaker_name": speaker,
            "text": text,
            "start_time": start,
            "end_time": start,
            "sequence_number": len(segments) + 1,
        })

    return segments


def analyze_imported_meeting(meeting_id: UUID) -> None:
    db = SessionLocal()

    try:
        meeting = meeting_service.get_meeting(db, meeting_id)

        if meeting is None:
            return

        meeting.status = MeetingStatus.PROCESSING
        meeting.processing_stage = "analyzing"
        db.commit()

        from app.services.analysis_service import analysis_service

        asyncio.run(
            analysis_service.analyze_meeting(
                db=db,
                meeting_id=meeting_id,
            )
        )

        db.expire_all()
        meeting = meeting_service.get_meeting(db, meeting_id)

        if meeting is not None:
            meeting.status = MeetingStatus.COMPLETED
            meeting.processing_stage = "completed"
            db.commit()

    except Exception as exc:
        db.rollback()
        print(f"[Transcript Analysis] {meeting_id}: {exc}")

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


@router.post("/from-transcript", response_model=MeetingResponse)
async def create_from_transcript(
    background_tasks: BackgroundTasks,
    title: str = Form(...),
    description: str | None = Form(None),
    meeting_type: MeetingType = Form(MeetingType.BUSINESS),
    transcript_text: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    if not title.strip():
        raise HTTPException(400, "Meeting title is required.")

    if len(title.strip()) > 255:
        raise HTTPException(400, "Meeting title is too long.")

    if file is not None and transcript_text and transcript_text.strip():
        raise HTTPException(400, "Provide a file or pasted text, not both.")

    original_filename = None

    if file is not None:
        original_filename = file.filename or "transcript.txt"

        if not original_filename.lower().endswith(".txt"):
            raise HTTPException(400, "Only .txt files are supported.")

        raw = await file.read(MAX_BYTES + 1)

        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "Transcript exceeds 2 MB.")

        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(400, "Transcript must be UTF-8 text.")
    else:
        content = transcript_text or ""

        if len(content.encode("utf-8")) > MAX_BYTES:
            raise HTTPException(413, "Transcript exceeds 2 MB.")

    segments = parse_transcript(content)

    if not segments:
        raise HTTPException(400, "Transcript is empty.")

    # Only create a new meeting; never overwrite existing transcripts.
    try:
        meeting = meeting_service.create_meeting(
            db,
            MeetingCreate(
                title=title.strip(),
                description=description,
                meeting_type=meeting_type,
            ),
        )

        for segment in segments:
            db.add(
                TranscriptSegment(
                    meeting_id=meeting.id,
                    speaker_label=None,
                    speaker_name=segment["speaker_name"],
                    text=segment["text"],
                    start_time=segment["start_time"],
                    end_time=segment["end_time"],
                    sequence_number=segment["sequence_number"],
                )
            )

        meeting.original_filename = original_filename
        meeting.status = MeetingStatus.PROCESSING
        meeting.processing_stage = "transcription_completed"

        db.commit()
        db.refresh(meeting)

    except Exception:
        db.rollback()
        raise

    background_tasks.add_task(analyze_imported_meeting, meeting.id)

    return meeting
