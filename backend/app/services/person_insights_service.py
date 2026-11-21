from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.person import Person
from app.models.participant import Participant
from app.models.meeting import Meeting
from app.models.commitment import Commitment


def get_person_insights(db: Session, person_id: UUID):
    person = db.get(Person, person_id)

    if person is None:
        return None

    participants = db.scalars(
        select(Participant)
        .where(Participant.person_id == person_id)
        .order_by(Participant.created_at, Participant.id)
    ).all()

    participant_ids = [item.id for item in participants]

    meeting_ids = list(dict.fromkeys(
        item.meeting_id for item in participants
    ))

    meetings = (
        db.scalars(
            select(Meeting)
            .where(Meeting.id.in_(meeting_ids))
            .order_by(Meeting.created_at, Meeting.id)
        ).all()
        if meeting_ids else []
    )

    commitments = (
        db.scalars(
            select(Commitment)
            .where(Commitment.owner_id.in_(participant_ids))
            .order_by(Commitment.created_at, Commitment.id)
        ).all()
        if participant_ids else []
    )

    today = date.today()
    tasks = []

    for commitment in commitments:
        status = getattr(
            commitment.status, "value", commitment.status
        )

        overdue = (
            status not in ("completed", "cancelled")
            and (
                status == "overdue"
                or (
                    commitment.deadline is not None
                    and commitment.deadline < today
                )
            )
        )

        tasks.append({
            "id": str(commitment.id),
            "meeting_id": str(commitment.meeting_id),
            "participant_id": str(commitment.owner_id),
            "task": commitment.task,
            "status": status,
            "deadline": (
                commitment.deadline.isoformat()
                if commitment.deadline else None
            ),
            "deadline_text": commitment.deadline_text,
            "overdue": overdue,
            "verification_status": commitment.verification_status,
        })

    meeting_items = [
        {
            "id": str(meeting.id),
            "title": meeting.title,
            "summary": meeting.summary,
            "created_at": (
                meeting.created_at.isoformat()
                if meeting.created_at else None
            ),
        }
        for meeting in meetings
    ]

    participant_items = [
        {
            "id": str(participant.id),
            "meeting_id": str(participant.meeting_id),
            "name": participant.name,
            "role": participant.role,
            "organization": participant.organization,
            "speaker_label": participant.speaker_label,
        }
        for participant in participants
    ]

    completed = sum(
        task["status"] == "completed" for task in tasks
    )
    cancelled = sum(
        task["status"] == "cancelled" for task in tasks
    )
    pending = sum(
        task["status"] not in ("completed", "cancelled")
        for task in tasks
    )
    overdue_count = sum(task["overdue"] for task in tasks)

    return {
        "person": {
            "id": str(person.id),
            "display_name": person.display_name,
        },
        "statistics": {
            "total_meetings": len(meeting_items),
            "total_participant_records": len(participant_items),
            "total_tasks": len(tasks),
            "pending_tasks": pending,
            "completed_tasks": completed,
            "cancelled_tasks": cancelled,
            "overdue_tasks": overdue_count,
            "completion_rate": (
                round(completed / (len(tasks) - cancelled) * 100, 1)
                if len(tasks) > cancelled else 0.0
            ),
        },
        "meetings": meeting_items,
        "participants": participant_items,
        "tasks": tasks,
        "requires_review": True,
    }
