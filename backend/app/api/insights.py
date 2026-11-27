from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.commitment import Commitment, CommitmentStatus
from app.models.meeting import Meeting
from app.models.participant import Participant
from app.models.person import Person


router = APIRouter(
    prefix="/insights",
    tags=["Insights"],
)


@router.get("/overview")
def get_overview_insights(db: Session = Depends(get_db)):
    today = date.today()

    # Total commitments
    total_commitments = db.scalar(select(func.count(Commitment.id))) or 0

    # Status breakdown
    status_counts = db.execute(
        select(Commitment.status, func.count(Commitment.id))
        .group_by(Commitment.status)
    ).all()

    status_map = {status.value: count for status, count in status_counts}

    completed = status_map.get("completed", 0)
    cancelled = status_map.get("cancelled", 0)
    in_progress = status_map.get("in_progress", 0)
    blocked = status_map.get("blocked", 0)
    open_count = status_map.get("open", 0)

    # Overdue count
    overdue_count = db.scalar(
        select(func.count(Commitment.id)).where(
            Commitment.deadline < today,
            Commitment.status.notin_([CommitmentStatus.COMPLETED, CommitmentStatus.CANCELLED])
        )
    ) or 0

    # Unassigned count
    unassigned_count = db.scalar(
        select(func.count(Commitment.id)).where(
            Commitment.owner_id.is_(None)
        )
    ) or 0

    # Completion rate
    active_total = total_commitments - cancelled
    completion_rate = round((completed / active_total * 100) if active_total > 0 else 0, 1)

    # Overdue rate
    overdue_rate = round((overdue_count / active_total * 100) if active_total > 0 else 0, 1)

    # Meeting-wise statistics
    meeting_stats = db.execute(
        select(
            Meeting.id,
            Meeting.title,
            func.count(Commitment.id).label("total_commitments"),
            func.count(Commitment.id).filter(Commitment.status == CommitmentStatus.COMPLETED).label("completed"),
            func.count(Commitment.id).filter(Commitment.deadline < today).filter(
                Commitment.status.notin_([CommitmentStatus.COMPLETED, CommitmentStatus.CANCELLED])
            ).label("overdue"),
        )
        .join(Commitment, Meeting.id == Commitment.meeting_id)
        .group_by(Meeting.id, Meeting.title)
        .order_by(func.count(Commitment.id).desc())
        .limit(20)
    ).all()

    meetings_data = [
        {
            "meeting_id": str(row.id),
            "meeting_title": row.title,
            "total_commitments": row.total_commitments,
            "completed": row.completed,
            "overdue": row.overdue,
            "completion_rate": round((row.completed / row.total_commitments * 100) if row.total_commitments > 0 else 0, 1),
        }
        for row in meeting_stats
    ]

    # Workload distribution by person
    person_stats = db.execute(
        select(
            Person.id,
            Person.display_name,
            func.count(Commitment.id).label("total_commitments"),
            func.count(Commitment.id).filter(Commitment.status == CommitmentStatus.COMPLETED).label("completed"),
            func.count(Commitment.id).filter(Commitment.deadline < today).filter(
                Commitment.status.notin_([CommitmentStatus.COMPLETED, CommitmentStatus.CANCELLED])
            ).label("overdue"),
        )
        .join(Participant, Person.id == Participant.person_id)
        .join(Commitment, Participant.id == Commitment.owner_id)
        .group_by(Person.id, Person.display_name)
        .order_by(func.count(Commitment.id).desc())
        .limit(20)
    ).all()

    workload_data = [
        {
            "person_id": str(row.id),
            "person_name": row.display_name,
            "total_commitments": row.total_commitments,
            "completed": row.completed,
            "overdue": row.overdue,
            "completion_rate": round((row.completed / row.total_commitments * 100) if row.total_commitments > 0 else 0, 1),
        }
        for row in person_stats
    ]

    # Total meetings
    total_meetings = db.scalar(select(func.count(Meeting.id))) or 0

    # Meetings with commitments
    meetings_with_commitments = db.scalar(
        select(func.count(func.distinct(Commitment.meeting_id)))
    ) or 0

    return {
        "summary": {
            "total_commitments": total_commitments,
            "completed": completed,
            "in_progress": in_progress,
            "blocked": blocked,
            "pending": open_count,
            "overdue": overdue_count,
            "cancelled": cancelled,
            "unassigned": unassigned_count,
            "completion_rate": completion_rate,
            "overdue_rate": overdue_rate,
            "total_meetings": total_meetings,
            "meetings_with_commitments": meetings_with_commitments,
        },
        "meetings": meetings_data,
        "workload": workload_data,
    }


@router.get("/meeting/{meeting_id}")
def get_meeting_insights(meeting_id: str, db: Session = Depends(get_db)):
    from uuid import UUID
    meeting_uuid = UUID(meeting_id)
    today = date.today()

    meeting = db.get(Meeting, meeting_uuid)
    if not meeting:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Meeting not found")

    commitments = db.scalars(
        select(Commitment).where(Commitment.meeting_id == meeting_uuid)
    ).all()

    total = len(commitments)
    completed = sum(1 for c in commitments if c.status == CommitmentStatus.COMPLETED)
    in_progress = sum(1 for c in commitments if c.status == CommitmentStatus.IN_PROGRESS)
    blocked = sum(1 for c in commitments if c.status == CommitmentStatus.BLOCKED)
    open_count = sum(1 for c in commitments if c.status == CommitmentStatus.OPEN)
    overdue = sum(1 for c in commitments if c.deadline and c.deadline < today and c.status not in [CommitmentStatus.COMPLETED, CommitmentStatus.CANCELLED])
    cancelled = sum(1 for c in commitments if c.status == CommitmentStatus.CANCELLED)
    unassigned = sum(1 for c in commitments if c.owner_id is None)

    active = total - cancelled
    completion_rate = round((completed / active * 100) if active > 0 else 0, 1)
    overdue_rate = round((overdue / active * 100) if active > 0 else 0, 1)

    # Participant breakdown
    participant_stats = {}
    for c in commitments:
        if c.owner_id:
            owner = db.get(Participant, c.owner_id)
            if owner:
                name = owner.name
                if name not in participant_stats:
                    participant_stats[name] = {"total": 0, "completed": 0, "overdue": 0}
                participant_stats[name]["total"] += 1
                if c.status == CommitmentStatus.COMPLETED:
                    participant_stats[name]["completed"] += 1
                if c.deadline and c.deadline < today and c.status not in [CommitmentStatus.COMPLETED, CommitmentStatus.CANCELLED]:
                    participant_stats[name]["overdue"] += 1

    participants_data = [
        {
            "name": name,
            "total": stats["total"],
            "completed": stats["completed"],
            "overdue": stats["overdue"],
            "completion_rate": round((stats["completed"] / stats["total"] * 100) if stats["total"] > 0 else 0, 1),
        }
        for name, stats in participant_stats.items()
    ]

    return {
        "meeting_id": str(meeting.id),
        "meeting_title": meeting.title,
        "summary": {
            "total_commitments": total,
            "completed": completed,
            "in_progress": in_progress,
            "blocked": blocked,
            "pending": open_count,
            "overdue": overdue,
            "cancelled": cancelled,
            "unassigned": unassigned,
            "completion_rate": completion_rate,
            "overdue_rate": overdue_rate,
        },
        "participants": participants_data,
    }