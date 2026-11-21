from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.transcript import TranscriptSegment


router = APIRouter(
    prefix="/transcripts",
    tags=["Transcript Search"],
)


class TranscriptSearchResult(BaseModel):
    id: UUID
    meeting_id: UUID
    speaker: str | None
    text: str
    start_time: float
    end_time: float


class TranscriptSearchResponse(BaseModel):
    query: str
    total: int
    results: list[TranscriptSearchResult]


@router.get(
    "/search",
    response_model=TranscriptSearchResponse,
)
def search_transcripts(
    q: str = Query(min_length=1, max_length=500),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = q.strip()

    if not query:
        return TranscriptSearchResponse(
            query=query,
            total=0,
            results=[],
        )

    # Treat user input as literal text, not SQL wildcard syntax.
    escaped = (
        query.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    pattern = f"%{escaped}%"

    condition = (
        TranscriptSegment.text.ilike(pattern, escape="\\")
        | TranscriptSegment.speaker_name.ilike(pattern, escape="\\")
        | TranscriptSegment.speaker_label.ilike(pattern, escape="\\")
    )

    total = db.scalar(
        select(func.count(TranscriptSegment.id)).where(condition)
    ) or 0

    segments = db.scalars(
        select(TranscriptSegment)
        .where(condition)
        .order_by(
            TranscriptSegment.meeting_id,
            TranscriptSegment.sequence_number,
        )
        .limit(limit)
    ).all()

    return TranscriptSearchResponse(
        query=query,
        total=total,
        results=[
            TranscriptSearchResult(
                id=segment.id,
                meeting_id=segment.meeting_id,
                speaker=(
                    segment.speaker_name
                    or segment.speaker_label
                ),
                text=segment.text,
                start_time=segment.start_time,
                end_time=segment.end_time,
            )
            for segment in segments
        ],
    )
