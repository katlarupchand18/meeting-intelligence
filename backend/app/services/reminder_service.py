from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.commitment import Commitment
from app.models.meeting import Meeting
from app.models.participant import Participant


def get_reminder_preview(db: Session, days_ahead: int = 7):
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    commitments = db.scalars(
        select(Commitment).order_by(Commitment.created_at.desc())
    ).all()

    meeting_ids = {c.meeting_id for c in commitments}
    owner_ids = {c.owner_id for c in commitments if c.owner_id}

    meetings = {
        m.id: m
        for m in db.scalars(
            select(Meeting).where(Meeting.id.in_(meeting_ids))
        ).all()
    } if meeting_ids else {}

    owners = {
        p.id: p
        for p in db.scalars(
            select(Participant).where(Participant.id.in_(owner_ids))
        ).all()
    } if owner_ids else {}

    groups = {
        "overdue": [],
        "upcoming": [],
        "needs_deadline_review": [],
        "no_deadline": [],
    }

    for commitment in commitments:
        status = getattr(
            commitment.status, "value", commitment.status
        )

        if status in ("completed", "cancelled"):
            continue

        meeting = meetings.get(commitment.meeting_id)
        owner = owners.get(commitment.owner_id)

        item = {
            "commitment_id": str(commitment.id),
            "meeting_id": str(commitment.meeting_id),
            "meeting_title": meeting.title if meeting else None,
            "owner_id": str(commitment.owner_id)
                if commitment.owner_id else None,
            "owner_name": owner.name if owner else None,
            "task": commitment.task,
            "status": status,
            "deadline": commitment.deadline.isoformat()
                if commitment.deadline else None,
            "deadline_text": commitment.deadline_text,
            "verification_status": commitment.verification_status,
        }

        if commitment.deadline is not None:
            if commitment.deadline < today:
                groups["overdue"].append(item)
            elif commitment.deadline <= cutoff:
                groups["upcoming"].append(item)
        elif commitment.deadline_text:
            groups["needs_deadline_review"].append(item)
        else:
            groups["no_deadline"].append(item)

    return {
        "today": today.isoformat(),
        "days_ahead": days_ahead,
        "counts": {
            key: len(value)
            for key, value in groups.items()
        },
        **groups,
        "delivery_enabled": False,
    }


def get_reminders_by_meeting(db: Session, days_ahead: int = 7, meeting_id: UUID | None = None):
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    query = select(Commitment).order_by(Commitment.created_at.desc())
    if meeting_id:
        query = query.where(Commitment.meeting_id == meeting_id)

    commitments = db.scalars(query).all()

    meeting_ids = {c.meeting_id for c in commitments}
    owner_ids = {c.owner_id for c in commitments if c.owner_id}

    meetings = {
        m.id: m
        for m in db.scalars(
            select(Meeting).where(Meeting.id.in_(meeting_ids))
        ).all()
    } if meeting_ids else {}

    owners = {
        p.id: p
        for p in db.scalars(
            select(Participant).where(Participant.id.in_(owner_ids))
        ).all()
    } if owner_ids else {}

    # Group by meeting
    meeting_groups = {}

    for commitment in commitments:
        status = getattr(commitment.status, "value", commitment.status)

        if status in ("completed", "cancelled"):
            continue

        meeting = meetings.get(commitment.meeting_id)
        owner = owners.get(commitment.owner_id)

        if not meeting:
            continue

        meeting_key = str(meeting.id)
        if meeting_key not in meeting_groups:
            meeting_groups[meeting_key] = {
                "meeting_id": meeting_key,
                "meeting_title": meeting.title,
                "overdue": [],
                "upcoming": [],
                "needs_deadline_review": [],
                "no_deadline": [],
            }

        item = {
            "commitment_id": str(commitment.id),
            "meeting_id": str(commitment.meeting_id),
            "meeting_title": meeting.title,
            "owner_id": str(commitment.owner_id) if commitment.owner_id else None,
            "owner_name": owner.name if owner else None,
            "task": commitment.task,
            "status": status,
            "deadline": commitment.deadline.isoformat() if commitment.deadline else None,
            "deadline_text": commitment.deadline_text,
            "verification_status": commitment.verification_status,
        }

        if commitment.deadline is not None:
            if commitment.deadline < today:
                meeting_groups[meeting_key]["overdue"].append(item)
            elif commitment.deadline <= cutoff:
                meeting_groups[meeting_key]["upcoming"].append(item)
        elif commitment.deadline_text:
            meeting_groups[meeting_key]["needs_deadline_review"].append(item)
        else:
            meeting_groups[meeting_key]["no_deadline"].append(item)

    # Convert to list and add counts
    result = []
    for meeting_key, groups in meeting_groups.items():
        total = sum(len(groups[k]) for k in ["overdue", "upcoming", "needs_deadline_review", "no_deadline"])
        if total > 0:
            result.append({
                "meeting_id": meeting_key,
                "meeting_title": groups["meeting_title"],
                "counts": {
                    "overdue": len(groups["overdue"]),
                    "upcoming": len(groups["upcoming"]),
                    "needs_deadline_review": len(groups["needs_deadline_review"]),
                    "no_deadline": len(groups["no_deadline"]),
                },
                "overdue": groups["overdue"],
                "upcoming": groups["upcoming"],
                "needs_deadline_review": groups["needs_deadline_review"],
                "no_deadline": groups["no_deadline"],
            })

    return {
        "today": today.isoformat(),
        "days_ahead": days_ahead,
        "meetings": result,
    }
