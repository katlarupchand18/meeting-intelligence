from uuid import UUID
from typing import Optional
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.meeting_chat_service import (
    meeting_chat_service,
    get_conversation,
    reset_conversation,
    set_conversation_meeting,
    ConversationContext,
)

logger = logging.getLogger(__name__)

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
    limit: int = Field(default=10, ge=1, le=50)
    similarity_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
    )
    use_fast_model: bool = Field(default=True, description="Use faster model for quicker responses")
    session_id: str | None = Field(default=None, description="Conversation session ID for memory")


class ChatSource(BaseModel):
    source_number: int
    meeting_id: str | None = None
    content: str
    similarity: float
    type: str
    retrieval_method: str
    metadata: dict = Field(default_factory=dict)


class ChatResponse(BaseModel):
    question: str
    answer: str
    sources: list[ChatSource] = Field(default_factory=list)
    intent: str | None = None
    provider: str | None = None
    note: str | None = None


class StreamEvent(BaseModel):
    type: str
    content: str | None = None
    question: str | None = None
    answer: str | None = None
    sources: list[ChatSource] | None = None
    error: str | None = None
    intent: str | None = None
    provider: str | None = None
    note: str | None = None


class ConversationHistoryResponse(BaseModel):
    session_id: str
    turns: list[dict] = Field(default_factory=list)
    current_meeting_id: str | None = None


class NewChatResponse(BaseModel):
    session_id: str
    message: str


@router.post(
    "/ask",
    response_model=ChatResponse,
)
async def ask_meeting_question(
    data: ChatRequest,
    db: Session = Depends(get_db),
):
    try:
        result = await meeting_chat_service.answer_question(
            db=db,
            question=data.question,
            meeting_id=data.meeting_id,
            limit=data.limit,
            similarity_threshold=data.similarity_threshold,
            use_fast_model=data.use_fast_model,
            session_id=data.session_id,
        )

        # Convert sources to ChatSource format
        sources = []
        for src in result.get("sources", []):
            sources.append(ChatSource(
                source_number=src.get("source_number", 0),
                meeting_id=src.get("meeting_id"),
                content=src.get("content", ""),
                similarity=src.get("similarity", 0.0),
                type=src.get("type", "unknown"),
                retrieval_method=src.get("retrieval_method", "unknown"),
                metadata=src.get("metadata", {}),
            ))

        return ChatResponse(
            question=result.get("question", data.question),
            answer=result.get("answer", ""),
            sources=sources,
            intent=result.get("intent"),
            provider=result.get("provider"),
            note=result.get("note"),
        )
    except Exception as e:
        # Do not expose internal errors or model configuration.
        logger.error(f"Meeting chat error: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Meeting AI chat is temporarily unavailable.",
        )


@router.post(
    "/ask/stream",
)
async def ask_meeting_question_stream(
    data: ChatRequest,
    db: Session = Depends(get_db),
):
    """Stream the answer to a meeting question."""
    try:
        async def event_generator():
            async for event in meeting_chat_service.answer_question_stream(
                db=db,
                question=data.question,
                meeting_id=data.meeting_id,
                limit=data.limit,
                similarity_threshold=data.similarity_threshold,
                use_fast_model=data.use_fast_model,
                session_id=data.session_id,
            ):
                # Convert sources if present
                if event.get("sources"):
                    event["sources"] = [
                        ChatSource(
                            source_number=src.get("source_number", 0),
                            meeting_id=src.get("meeting_id"),
                            content=src.get("content", ""),
                            similarity=src.get("similarity", 0.0),
                            type=src.get("type", "unknown"),
                            retrieval_method=src.get("retrieval_method", "unknown"),
                            metadata=src.get("metadata", {}),
                        )
                        for src in event["sources"]
                    ]
                yield f"data: {StreamEvent(**event).model_dump_json()}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as e:
        logger.error(f"Meeting chat streaming error: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Meeting AI chat streaming is temporarily unavailable.",
        )


@router.post(
    "/new",
    response_model=NewChatResponse,
)
async def new_chat():
    """Start a new conversation (reset memory)."""
    import uuid
    session_id = str(uuid.uuid4())
    # Ensure conversation exists
    get_conversation(session_id)
    return NewChatResponse(
        session_id=session_id,
        message="New conversation started. Your previous context has been cleared."
    )


@router.get(
    "/history/{session_id}",
    response_model=ConversationHistoryResponse,
)
async def get_chat_history(session_id: str):
    """Get conversation history for a session."""
    conversation = get_conversation(session_id)

    turns = []
    for turn in conversation.turns:
        turns.append({
            "role": turn.role,
            "content": turn.content,
            "timestamp": turn.timestamp.isoformat(),
            "metadata": turn.metadata,
        })

    return ConversationHistoryResponse(
        session_id=session_id,
        turns=turns,
        current_meeting_id=str(conversation.current_meeting_id) if conversation.current_meeting_id else None,
    )


@router.delete(
    "/history/{session_id}",
    response_model=NewChatResponse,
)
async def clear_chat_history(session_id: str):
    """Clear conversation history (same as new chat)."""
    reset_conversation(session_id)
    import uuid
    new_session_id = str(uuid.uuid4())
    get_conversation(new_session_id)
    return NewChatResponse(
        session_id=new_session_id,
        message="Conversation history cleared. Started new session."
    )


@router.post(
    "/history/{session_id}/meeting/{meeting_id}",
)
async def set_chat_meeting_context(
    session_id: str,
    meeting_id: UUID,
):
    """Set the meeting context for a conversation session."""
    set_conversation_meeting(session_id, meeting_id)
    return {"message": f"Meeting context set to {meeting_id}", "session_id": session_id}


@router.get(
    "/providers",
)
async def get_available_providers():
    """Get information about available LLM providers."""
    from app.services.llm_service import llm_service
    return llm_service.get_provider_info()