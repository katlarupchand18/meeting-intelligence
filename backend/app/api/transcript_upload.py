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

# Pattern for timestamped speaker lines: [HH:MM – HH:MM] Speaker Name:
# or [HH:MM] Speaker Name:
TIMESTAMP_SPEAKER_PATTERN = re.compile(
    r"^\[(?P<start_time>\d{1,2}:\d{2}(?::\d{2})?)\s*[–-]\s*(?P<end_time>\d{1,2}:\d{2}(?::\d{2})?)\]\s*(?P<speaker>[^:\n]{1,100}):\s*$"
)

# Pattern for simple timestamped speaker lines: [HH:MM] Speaker Name:
SIMPLE_TIMESTAMP_PATTERN = re.compile(
    r"^\[(?P<time>\d{1,2}:\d{2}(?::\d{2})?)\]\s*(?P<speaker>[^:\n]{1,100}):\s*$"
)

# Pattern for speaker lines without timestamps: Speaker Name:
SPEAKER_PATTERN = re.compile(
    r"^(?P<speaker>[^:\n]{1,100}):\s*(?P<text>.+)$"
)


def parse_time(value: str | None) -> float:
    if not value:
        return 0.0

    parts = [int(part) for part in value.split(":")]

    if len(parts) == 2:
        return float(parts[0] * 60 + parts[1])

    return float(parts[0] * 3600 + parts[1] * 60 + parts[2])


def parse_transcript(content: str) -> list[dict]:
    """
    Parse transcript supporting multiple formats:
    1. [HH:MM – HH:MM] Speaker Name:\nText on next line(s)
    2. [MM:SS – MM:SS] Speaker Name:\nText on next line(s)
    3. [HH:MM] Speaker Name:\nText on next line(s)
    4. Speaker Name: Text on same line
    5. Plain text lines (no speaker)
    """
    segments = []
    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()  # Keep leading spaces for pattern matching

        if not line.strip():
            i += 1
            continue

        speaker = None
        start_time = 0.0
        end_time = 0.0
        text = ""

        # Try timestamp RANGE pattern FIRST (most specific): [HH:MM – HH:MM] Speaker: or [MM:SS – MM:SS] Speaker:
        match = TIMESTAMP_SPEAKER_PATTERN.match(line)
        if match:
            speaker = match.group("speaker").strip()
            start_time = parse_time(match.group("start_time"))
            end_time = parse_time(match.group("end_time"))
            # Text is on subsequent lines until next speaker/timestamp
            i += 1
            text_lines = []
            while i < len(lines):
                next_line = lines[i].rstrip()
                if not next_line.strip():
                    i += 1
                    continue
                # Check if next line is a new speaker/timestamp
                next_stripped = next_line.strip()
                if (TIMESTAMP_SPEAKER_PATTERN.match(next_stripped) or
                    SIMPLE_TIMESTAMP_PATTERN.match(next_stripped) or
                    SPEAKER_PATTERN.match(next_stripped)):
                    break
                text_lines.append(next_line.strip())
                i += 1
            text = " ".join(text_lines).strip()

        # Try simple timestamp pattern: [HH:MM] Speaker: or [MM:SS] Speaker:
        elif SIMPLE_TIMESTAMP_PATTERN.match(line.strip()):
            match = SIMPLE_TIMESTAMP_PATTERN.match(line.strip())
            speaker = match.group("speaker").strip()
            start_time = parse_time(match.group("time"))
            end_time = start_time
            # Text is on subsequent lines
            i += 1
            text_lines = []
            while i < len(lines):
                next_line = lines[i].rstrip()
                if not next_line.strip():
                    i += 1
                    continue
                next_stripped = next_line.strip()
                if (TIMESTAMP_SPEAKER_PATTERN.match(next_stripped) or
                    SIMPLE_TIMESTAMP_PATTERN.match(next_stripped) or
                    SPEAKER_PATTERN.match(next_stripped)):
                    break
                text_lines.append(next_line.strip())
                i += 1
            text = " ".join(text_lines).strip()

        # Try speaker pattern: Speaker: Text (on same line)
        elif SPEAKER_PATTERN.match(line.strip()):
            match = SPEAKER_PATTERN.match(line.strip())
            speaker = match.group("speaker").strip()
            text = match.group("text").strip()
            start_time = 0.0
            end_time = 0.0
            i += 1

        # Plain text line (no speaker)
        else:
            speaker = None
            text = line.strip()
            start_time = 0.0
            end_time = 0.0
            i += 1

        if not text:
            continue

        segments.append({
            "speaker_name": speaker,
            "text": text,
            "start_time": start_time,
            "end_time": end_time,
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
