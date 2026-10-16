from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.meeting import MeetingStatus, MeetingType


class MeetingCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    meeting_type: MeetingType = MeetingType.GENERAL


class MeetingUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    meeting_type: MeetingType | None = None
    status: MeetingStatus | None = None


class MeetingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str | None = None
    meeting_type: MeetingType
    status: MeetingStatus
    processing_stage: str = "uploaded"
    original_filename: str | None = None
    duration_seconds: int | None = None
    summary: str | None = None
    created_at: datetime
    updated_at: datetime


class MeetingListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[MeetingResponse]
    total: int
    page: int
    page_size: int
    total_pages: int