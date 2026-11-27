"""
Schemas for Meeting Chat API.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID
from pydantic import BaseModel, Field


class ChatSource(BaseModel):
    """Source citation for chat response."""
    source_number: int
    meeting_id: str | None = None
    content: str
    similarity: float = 0.0
    type: str
    retrieval_method: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    """Chat message in conversation."""
    role: str  # user, assistant
    content: str
    sources: list[ChatSource] | None = None


class ChatRequest(BaseModel):
    """Request to chat with meeting data."""
    question: str
    meeting_id: UUID | None = None
    limit: int = 10
    similarity_threshold: float = 0.60
    use_fast_model: bool = True


class ChatResponse(BaseModel):
    """Response from chat with meeting data."""
    question: str
    answer: str
    sources: list[ChatSource] = Field(default_factory=list)


class ChatStreamEvent(BaseModel):
    """Streaming chat event."""
    type: str  # sources, content, done, error
    content: str | None = None
    sources: list[ChatSource] | None = None
    question: str | None = None
    answer: str | None = None
    error: str | None = None