from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.meeting_chat_service import meeting_chat_service


router = APIRouter(
    prefix="/chat",
    tags=["AI Meeting Chat"],
)


class ChatRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
    )
    meeting_id: UUID | None = None
    limit: int = Field(default=5, ge=1, le=20)
    similarity_threshold: float = Field(
        default=0.60,
        ge=0.0,
        le=1.0,
    )


class ChatSource(BaseModel):
    source_number: int
    meeting_id: UUID
    content: str
    similarity: float


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[ChatSource]


@router.post(
    "/ask",
    response_model=ChatResponse,
)
async def ask_meeting_question(
    data: ChatRequest,
    db: Session = Depends(get_db),
):
    try:
        return await meeting_chat_service.answer_question(
            db=db,
            question=data.question,
            meeting_id=data.meeting_id,
            limit=data.limit,
            similarity_threshold=data.similarity_threshold,
        )
    except Exception:
        # Do not expose internal errors or model configuration.
        raise HTTPException(
            status_code=503,
            detail="Meeting AI chat is temporarily unavailable.",
        )
