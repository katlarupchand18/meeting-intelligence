from uuid import UUID
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.meeting import Meeting
from app.models.commitment import Commitment, CommitmentStatus
from app.models.decision import Decision, DecisionStatus
from app.models.participant import Participant
from app.models.transcript import TranscriptSegment
from app.services.llm_service import llm_service


router = APIRouter(
    prefix="/comparison",
    tags=["Meeting Comparison"],
)


class CommitmentComparison(BaseModel):
    meeting_a_id: str
    meeting_b_id: str
    meeting_a_title: str
    meeting_b_title: str
    meeting_a_date: str
    meeting_b_date: str
    new_commitments: list[dict]
    completed_commitments: list[dict]
    pending_commitments: list[dict]
    changed_deadlines: list[dict]
    changed_ownership: list[dict]
    not_mentioned_again: list[dict]


class DecisionComparison(BaseModel):
    meeting_a_id: str
    meeting_b_id: str
    meeting_a_title: str
    meeting_b_title: str
    meeting_a_date: str
    meeting_b_date: str
    new_decisions: list[dict]
    changed_decisions: list[dict]
    superseded_decisions: list[dict]
    not_mentioned_again: list[dict]


class TranscriptExcerpt(BaseModel):
    meeting_id: str
    meeting_title: str
    speaker: Optional[str]
    text: str
    start_time: float
    end_time: float


class ComparisonResponse(BaseModel):
    meeting_a: dict
    meeting_b: dict
    commitments: CommitmentComparison
    decisions: DecisionComparison
    relevant_excerpts: list[TranscriptExcerpt]
    followup_questions: list[str]
    summary: str


def get_meeting_data(db: Session, meeting_id: UUID) -> dict:
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        return None

    commitments = db.scalars(
        select(Commitment).where(Commitment.meeting_id == meeting_id)
    ).all()

    decisions = db.scalars(
        select(Decision).where(Decision.meeting_id == meeting_id)
    ).all()

    segments = db.scalars(
        select(TranscriptSegment)
        .where(TranscriptSegment.meeting_id == meeting_id)
        .order_by(TranscriptSegment.sequence_number)
        .limit(100)
    ).all()

    participants = db.scalars(
        select(Participant).where(Participant.meeting_id == meeting_id)
    ).all()

    participant_map = {p.id: p.name for p in participants}

    return {
        "meeting": meeting,
        "commitments": [
            {
                "id": str(c.id),
                "task": c.task,
                "status": c.status.value,
                "deadline": c.deadline.isoformat() if c.deadline else None,
                "deadline_text": c.deadline_text,
                "owner_id": str(c.owner_id) if c.owner_id else None,
                "owner_name": participant_map.get(c.owner_id) if c.owner_id else None,
                "strength": c.strength.value,
            }
            for c in commitments
        ],
        "decisions": [
            {
                "id": str(d.id),
                "title": d.title,
                "description": d.description,
                "status": d.status.value,
            }
            for d in decisions
        ],
        "transcript": [
            {
                "id": str(s.id),
                "speaker": s.speaker_name or s.speaker_label,
                "text": s.text,
                "start_time": s.start_time,
                "end_time": s.end_time,
            }
            for s in segments
        ],
    }


def compare_commitments(meeting_a: dict, meeting_b: dict) -> dict:
    """Compare commitments between two meetings."""
    commitments_a = meeting_a["commitments"]
    commitments_b = meeting_b["commitments"]

    # Create lookup maps for meeting A
    a_by_task = {c["task"].lower().strip(): c for c in commitments_a}
    a_by_id = {c["id"]: c for c in commitments_a}

    new_commitments = []
    completed_commitments = []
    pending_commitments = []
    changed_deadlines = []
    changed_ownership = []
    not_mentioned_again = []

    # Check commitments in B
    matched_a_ids = set()
    for c_b in commitments_b:
        task_key = c_b["task"].lower().strip()
        if task_key in a_by_task:
            c_a = a_by_task[task_key]
            matched_a_ids.add(c_a["id"])

            # Check if completed in A but still in B
            if c_a["status"] == "completed" and c_b["status"] != "completed":
                completed_commitments.append({
                    "task": c_b["task"],
                    "meeting_a_status": c_a["status"],
                    "meeting_b_status": c_b["status"],
                    "meeting_a_deadline": c_a["deadline"],
                    "meeting_b_deadline": c_b["deadline"],
                })

            # Check deadline changes
            if c_a["deadline"] != c_b["deadline"]:
                changed_deadlines.append({
                    "task": c_b["task"],
                    "meeting_a_deadline": c_a["deadline"],
                    "meeting_b_deadline": c_b["deadline"],
                    "meeting_a_deadline_text": c_a["deadline_text"],
                    "meeting_b_deadline_text": c_b["deadline_text"],
                })

            # Check ownership changes
            if c_a["owner_id"] != c_b["owner_id"]:
                changed_ownership.append({
                    "task": c_b["task"],
                    "meeting_a_owner": c_a["owner_name"],
                    "meeting_b_owner": c_b["owner_name"],
                })

            # Check if still pending
            if c_b["status"] in ["open", "in_progress", "blocked"]:
                pending_commitments.append({
                    "task": c_b["task"],
                    "status": c_b["status"],
                    "deadline": c_b["deadline"],
                    "owner": c_b["owner_name"],
                })
        else:
            # New commitment in B
            new_commitments.append({
                "task": c_b["task"],
                "status": c_b["status"],
                "deadline": c_b["deadline"],
                "deadline_text": c_b["deadline_text"],
                "owner": c_b["owner_name"],
            })

    # Commitments in A not mentioned in B
    for c_a in commitments_a:
        if c_a["id"] not in matched_a_ids:
            not_mentioned_again.append({
                "task": c_a["task"],
                "status": c_a["status"],
                "deadline": c_a["deadline"],
                "deadline_text": c_a["deadline_text"],
                "owner": c_a["owner_name"],
            })

    return {
        "new_commitments": new_commitments,
        "completed_commitments": completed_commitments,
        "pending_commitments": pending_commitments,
        "changed_deadlines": changed_deadlines,
        "changed_ownership": changed_ownership,
        "not_mentioned_again": not_mentioned_again,
    }


def compare_decisions(meeting_a: dict, meeting_b: dict) -> dict:
    """Compare decisions between two meetings."""
    decisions_a = meeting_a["decisions"]
    decisions_b = meeting_b["decisions"]

    a_by_title = {d["title"].lower().strip(): d for d in decisions_a}

    new_decisions = []
    changed_decisions = []
    superseded_decisions = []
    not_mentioned_again = []

    matched_a_ids = set()
    for d_b in decisions_b:
        title_key = d_b["title"].lower().strip()
        if title_key in a_by_title:
            d_a = a_by_title[title_key]
            matched_a_ids.add(d_a["id"])

            # Check if decision changed
            if d_a["description"] != d_b["description"] or d_a["status"] != d_b["status"]:
                changed_decisions.append({
                    "title": d_b["title"],
                    "meeting_a_description": d_a["description"],
                    "meeting_b_description": d_b["description"],
                    "meeting_a_status": d_a["status"],
                    "meeting_b_status": d_b["status"],
                })

            # Check if superseded
            if d_a["status"] in ["accepted", "proposed"] and d_b["status"] in ["changed", "superseded"]:
                superseded_decisions.append({
                    "title": d_b["title"],
                    "meeting_a_status": d_a["status"],
                    "meeting_b_status": d_b["status"],
                })
        else:
            new_decisions.append({
                "title": d_b["title"],
                "description": d_b["description"],
                "status": d_b["status"],
            })

    for d_a in decisions_a:
        if d_a["id"] not in matched_a_ids:
            not_mentioned_again.append({
                "title": d_a["title"],
                "description": d_a["description"],
                "status": d_a["status"],
            })

    return {
        "new_decisions": new_decisions,
        "changed_decisions": changed_decisions,
        "superseded_decisions": superseded_decisions,
        "not_mentioned_again": not_mentioned_again,
    }


def find_relevant_excerpts(meeting_a: dict, meeting_b: dict, max_per_meeting: int = 5) -> list[dict]:
    """Find relevant transcript excerpts from both meetings."""
    excerpts = []

    # Get key topics from commitments and decisions
    keywords = set()
    for c in meeting_a["commitments"] + meeting_b["commitments"]:
        words = c["task"].lower().split()
        keywords.update(w for w in words if len(w) > 4)
    for d in meeting_a["decisions"] + meeting_b["decisions"]:
        words = d["title"].lower().split()
        keywords.update(w for w in words if len(w) > 4)

    # Score segments by keyword overlap
    for meeting_data, meeting_key in [(meeting_a, "a"), (meeting_b, "b")]:
        scored = []
        for seg in meeting_data["transcript"]:
            text_lower = seg["text"].lower()
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scored.append((score, seg))

        scored.sort(key=lambda x: -x[0])
        for score, seg in scored[:max_per_meeting]:
            excerpts.append({
                "meeting_id": str(meeting_data["meeting"].id),
                "meeting_title": meeting_data["meeting"].title,
                "speaker": seg["speaker"],
                "text": seg["text"],
                "start_time": seg["start_time"],
                "end_time": seg["end_time"],
            })

    return excerpts


def generate_followup_questions(
    commitment_comparison: dict,
    decision_comparison: dict,
    meeting_a_title: str,
    meeting_b_title: str,
) -> list[str]:
    """Generate follow-up questions based on the comparison."""
    questions = []

    # New commitments
    for c in commitment_comparison["new_commitments"][:3]:
        questions.append(f"Who is responsible for the new commitment: '{c['task']}' from {meeting_b_title}?")

    # Changed deadlines
    for c in commitment_comparison["changed_deadlines"][:3]:
        questions.append(f"The deadline for '{c['task']}' changed from {c['meeting_a_deadline'] or 'unspecified'} to {c['meeting_b_deadline'] or 'unspecified'}. What prompted this change?")

    # Changed ownership
    for c in commitment_comparison["changed_ownership"][:3]:
        questions.append(f"Ownership of '{c['task']}' changed from {c['meeting_a_owner'] or 'unassigned'} to {c['meeting_b_owner'] or 'unassigned'}. Was this intentional?")

    # Not mentioned again
    for c in commitment_comparison["not_mentioned_again"][:3]:
        if c["status"] not in ["completed", "cancelled"]:
            questions.append(f"'{c['task']}' from {meeting_a_title} was not mentioned in {meeting_b_title}. Is this still pending?")

    # New decisions
    for d in decision_comparison["new_decisions"][:3]:
        questions.append(f"New decision in {meeting_b_title}: '{d['title']}'. What are the next steps?")

    # Changed decisions
    for d in decision_comparison["changed_decisions"][:3]:
        questions.append(f"Decision '{d['title']}' changed from '{d['meeting_a_status']}' to '{d['meeting_b_status']}'. What changed?")

    return questions[:10]


@router.post("/compare", response_model=ComparisonResponse)
async def compare_meetings(
    meeting_a_id: UUID = Query(..., description="Earlier meeting ID"),
    meeting_b_id: UUID = Query(..., description="Later meeting ID"),
    db: Session = Depends(get_db),
):
    if meeting_a_id == meeting_b_id:
        raise HTTPException(status_code=400, detail="Choose two different meetings.")

    meeting_a = get_meeting_data(db, meeting_a_id)
    meeting_b = get_meeting_data(db, meeting_b_id)

    if not meeting_a or not meeting_b:
        raise HTTPException(status_code=404, detail="One or both meetings not found.")

    # Ensure meeting_a is earlier
    if meeting_a["meeting"].created_at > meeting_b["meeting"].created_at:
        meeting_a, meeting_b = meeting_b, meeting_a

    # Compare commitments and decisions
    commitment_comparison = compare_commitments(meeting_a, meeting_b)
    decision_comparison = compare_decisions(meeting_a, meeting_b)

    # Find relevant transcript excerpts
    excerpts = find_relevant_excerpts(meeting_a, meeting_b)

    # Generate follow-up questions
    followup_questions = generate_followup_questions(
        commitment_comparison,
        decision_comparison,
        meeting_a["meeting"].title,
        meeting_b["meeting"].title,
    )

    # Generate summary using LLM
    summary_prompt = f"""
Compare Meeting A ({meeting_a['meeting'].title}, {meeting_a['meeting'].created_at.date()}) and Meeting B ({meeting_b['meeting'].title}, {meeting_b['meeting'].created_at.date()}).

Commitment changes:
- New: {len(commitment_comparison['new_commitments'])}
- Completed: {len(commitment_comparison['completed_commitments'])}
- Pending: {len(commitment_comparison['pending_commitments'])}
- Deadline changes: {len(commitment_comparison['changed_deadlines'])}
- Ownership changes: {len(commitment_comparison['changed_ownership'])}
- Not mentioned again: {len(commitment_comparison['not_mentioned_again'])}

Decision changes:
- New: {len(decision_comparison['new_decisions'])}
- Changed: {len(decision_comparison['changed_decisions'])}
- Superseded: {len(decision_comparison['superseded_decisions'])}
- Not mentioned again: {len(decision_comparison['not_mentioned_again'])}

Write a concise 3-4 sentence summary of the key differences and action items for follow-up.
"""

    try:
        summary = llm_service.generate(
            prompt=summary_prompt,
            system_prompt="You are a meeting analyst. Write concise, factual summaries.",
        )
    except Exception:
        summary = f"Compared {meeting_a['meeting'].title} and {meeting_b['meeting'].title}. Found {len(commitment_comparison['new_commitments'])} new commitments, {len(commitment_comparison['changed_deadlines'])} deadline changes, and {len(decision_comparison['new_decisions'])} new decisions."

    return ComparisonResponse(
        meeting_a={
            "id": str(meeting_a["meeting"].id),
            "title": meeting_a["meeting"].title,
            "date": meeting_a["meeting"].created_at.isoformat(),
        },
        meeting_b={
            "id": str(meeting_b["meeting"].id),
            "title": meeting_b["meeting"].title,
            "date": meeting_b["meeting"].created_at.isoformat(),
        },
        commitments=CommitmentComparison(
            meeting_a_id=str(meeting_a["meeting"].id),
            meeting_b_id=str(meeting_b["meeting"].id),
            meeting_a_title=meeting_a["meeting"].title,
            meeting_b_title=meeting_b["meeting"].title,
            meeting_a_date=meeting_a["meeting"].created_at.isoformat(),
            meeting_b_date=meeting_b["meeting"].created_at.isoformat(),
            **commitment_comparison,
        ),
        decisions=DecisionComparison(
            meeting_a_id=str(meeting_a["meeting"].id),
            meeting_b_id=str(meeting_b["meeting"].id),
            meeting_a_title=meeting_a["meeting"].title,
            meeting_b_title=meeting_b["meeting"].title,
            meeting_a_date=meeting_a["meeting"].created_at.isoformat(),
            meeting_b_date=meeting_b["meeting"].created_at.isoformat(),
            **decision_comparison,
        ),
        relevant_excerpts=excerpts,
        followup_questions=followup_questions,
        summary=summary,
    )


@router.get("/suggestions")
async def get_meeting_suggestions(
    meeting_id: UUID = Query(..., description="Reference meeting ID"),
    db: Session = Depends(get_db),
):
    """Get related meeting suggestions based on shared participants, topics, or time proximity."""
    meeting = db.get(Meeting, meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found.")

    # Get participants of this meeting
    participants = db.scalars(
        select(Participant).where(Participant.meeting_id == meeting_id)
    ).all()
    participant_names = {p.name for p in participants}

    # Find other meetings with shared participants
    other_meetings = db.scalars(
        select(Meeting)
        .where(Meeting.id != meeting_id)
        .where(Meeting.status == "completed")
        .order_by(Meeting.created_at.desc())
        .limit(50)
    ).all()

    suggestions = []
    for m in other_meetings:
        m_participants = db.scalars(
            select(Participant).where(Participant.meeting_id == m.id)
        ).all()
        m_names = {p.name for p in m_participants}

        shared = participant_names & m_names
        score = len(shared)

        # Also consider time proximity
        days_diff = abs((m.created_at - meeting.created_at).days)
        if days_diff <= 30:
            score += 2

        if score > 0:
            suggestions.append({
                "meeting_id": str(m.id),
                "title": m.title,
                "date": m.created_at.isoformat(),
                "shared_participants": list(shared),
                "score": score,
            })

    # Sort by score
    suggestions.sort(key=lambda x: -x["score"])

    return {
        "reference_meeting": {
            "id": str(meeting.id),
            "title": meeting.title,
        },
        "suggestions": suggestions[:10],
    }