from uuid import UUID

from pydantic import BaseModel, Field


class MemorySearchRequest(BaseModel):
    """
    Request for searching information across previous meetings.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )

    meeting_id: UUID | None = None

    limit: int = Field(
        default=10,
        ge=1,
        le=50,
    )

    similarity_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
    )


class MemorySearchResult(BaseModel):
    """
    A single semantic-memory search result.
    """

    meeting_id: UUID

    content: str

    similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
    )


class MemorySearchResponse(BaseModel):
    """
    Semantic search response.
    """

    query: str

    results: list[MemorySearchResult]

    total: int