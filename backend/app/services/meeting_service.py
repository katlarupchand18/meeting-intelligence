from math import ceil
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.meeting import Meeting, MeetingStatus, MeetingType
from app.schemas.meeting import MeetingCreate, MeetingUpdate


class MeetingService:
    """
    Business logic for creating, retrieving, updating,
    and deleting meetings.
    """

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    def create_meeting(
        self,
        db: Session,
        data: MeetingCreate,
    ) -> Meeting:
        meeting = Meeting(
            title=data.title.strip(),
            description=(
                data.description.strip()
                if data.description
                else None
            ),
            meeting_type=data.meeting_type,
            status=MeetingStatus.UPLOADED,
        )

        db.add(meeting)
        db.commit()
        db.refresh(meeting)

        return meeting

    # ---------------------------------------------------------
    # Get One
    # ---------------------------------------------------------

    def get_meeting(
        self,
        db: Session,
        meeting_id: UUID,
    ) -> Meeting | None:
        return db.scalar(
            select(Meeting).where(
                Meeting.id == meeting_id
            )
        )

    # ---------------------------------------------------------
    # List
    # ---------------------------------------------------------

    def list_meetings(
        self,
        db: Session,
        page: int = 1,
        page_size: int = 20,
        status: MeetingStatus | None = None,
        meeting_type: MeetingType | None = None,
    ) -> tuple[list[Meeting], int, int]:

        page = max(1, page)
        page_size = min(
            max(1, page_size),
            100,
        )

        filters = []

        if status is not None:
            filters.append(
                Meeting.status == status
            )

        if meeting_type is not None:
            filters.append(
                Meeting.meeting_type == meeting_type
            )

        total = db.scalar(
            select(func.count(Meeting.id)).where(
                *filters
            )
        ) or 0

        total_pages = max(
            1,
            ceil(total / page_size),
        )

        meetings = list(
            db.scalars(
                select(Meeting)
                .where(*filters)
                .order_by(
                    Meeting.created_at.desc()
                )
                .offset(
                    (page - 1) * page_size
                )
                .limit(page_size)
            ).all()
        )

        return (
            meetings,
            total,
            total_pages,
        )

    # ---------------------------------------------------------
    # Update
    # ---------------------------------------------------------

    def update_meeting(
        self,
        db: Session,
        meeting: Meeting,
        data: MeetingUpdate,
    ) -> Meeting:

        updates = data.model_dump(
            exclude_unset=True
        )

        for field, value in updates.items():

            if isinstance(value, str):
                value = value.strip()

            setattr(
                meeting,
                field,
                value,
            )

        db.commit()
        db.refresh(meeting)

        return meeting

    # ---------------------------------------------------------
    # Processing Status
    # ---------------------------------------------------------

    def update_status(
        self,
        db: Session,
        meeting: Meeting,
        status: MeetingStatus,
    ) -> Meeting:

        meeting.status = status

        db.commit()
        db.refresh(meeting)

        return meeting

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    def update_summary(
        self,
        db: Session,
        meeting: Meeting,
        summary: str,
    ) -> Meeting:

        meeting.summary = summary.strip()

        db.commit()
        db.refresh(meeting)

        return meeting

    # ---------------------------------------------------------
    # Uploaded File
    # ---------------------------------------------------------

    def attach_file(
        self,
        db: Session,
        meeting: Meeting,
        file_path: str,
        original_filename: str,
    ) -> Meeting:

        meeting.file_path = file_path
        meeting.original_filename = (
            original_filename
        )

        db.commit()
        db.refresh(meeting)

        return meeting

    # ---------------------------------------------------------
    # Duration
    # ---------------------------------------------------------

    def update_duration(
        self,
        db: Session,
        meeting: Meeting,
        duration_seconds: float,
    ) -> Meeting:

        meeting.duration_seconds = max(
            0,
            round(duration_seconds),
        )

        db.commit()
        db.refresh(meeting)

        return meeting

    # ---------------------------------------------------------
    # Delete
    # ---------------------------------------------------------

    def delete_meeting(
        self,
        db: Session,
        meeting: Meeting,
    ) -> None:

        db.delete(meeting)
        db.commit()


meeting_service = MeetingService()