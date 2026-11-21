from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.participant import Participant
from app.models.meeting import Meeting
from app.models.commitment import Commitment
from app.models.decision import Decision


def get_participant_insights(db: Session, participant_id: UUID):
    participant = db.get(Participant, participant_id)

    if participant is None:
        return None

    meeting = db.get(Meeting, participant.meeting_id)

    if meeting is None:
        return None

    commitments = db.scalars(
        select(Commitment)
        .where(Commitment.owner_id == participant.id)
        .where(Commitment.meeting_id == meeting.id)
    ).all()

    decisions = db.scalars(
        select(Decision)
        .where(Decision.meeting_id == meeting.id)
    ).all()

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

    decision_items = []

    for decision in decisions:
        status = getattr(
            decision.status, "value", decision.status
        )

        if status in ("rejected", "changed", "superseded"):
            continue

        if decision.verification_status == "rejected":
            continue

        decision_items.append({
            "id": str(decision.id),
            "title": decision.title,
            "description": decision.description,
            "status": status,
            "verification_status": decision.verification_status,
        })

    return {
        "participant": {
            "id": str(participant.id),
            "name": participant.name,
            "role": participant.role,
            "organization": participant.organization,
            "speaker_label": participant.speaker_label,
        },
        "meeting": {
            "id": str(meeting.id),
            "title": meeting.title,
            "summary": meeting.summary,
            "created_at": (
                meeting.created_at.isoformat()
                if meeting.created_at else None
            ),
        },
        "statistics": {
            "total_tasks": len(tasks),
            "pending_tasks": sum(
                task["status"] not in ("completed", "cancelled")
                for task in tasks
            ),
            "completed_tasks": sum(
                task["status"] == "completed"
                for task in tasks
            ),
            "overdue_tasks": sum(
                task["overdue"] for task in tasks
            ),
            "meeting_decisions": len(decision_items),
        },
        "tasks": tasks,
        "meeting_decisions": decision_items,
        "requires_review": True,
    }
