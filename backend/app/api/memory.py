from uuid import UUID
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.memory import (
    MemorySearchRequest,
    MemorySearchResponse,
)
from app.services.memory_service import (
    memory_service,
)


router = APIRouter(
    prefix="/memory",
    tags=["Cross-Meeting Memory"],
)


# ---------------------------------------------------------
# Semantic Search
# ---------------------------------------------------------

@router.post(
    "/search",
    response_model=MemorySearchResponse,
)
async def search_memory(
    data: MemorySearchRequest,
    db: Session = Depends(get_db),
):

    try:
        return await memory_service.search_memory(
            db=db,
            query=data.query,
            limit=data.limit,
            similarity_threshold=(
                data.similarity_threshold if data.similarity_threshold is not None else 0.35
            ),
            meeting_id=data.meeting_id,
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Memory search failed: "
                f"{str(exc)}"
            ),
        ) from exc


# ---------------------------------------------------------
# Enhanced Search with Filters
# ---------------------------------------------------------

@router.get(
    "/search",
    response_model=MemorySearchResponse,
)
async def search_memory_get(
    q: str = Query(..., min_length=1, max_length=2000),
    limit: int = Query(default=20, ge=1, le=100),
    similarity_threshold: float = Query(default=0.35, ge=0.0, le=1.0),
    meeting_id: Optional[UUID] = Query(default=None),
    result_type: Optional[str] = Query(default=None, pattern="^(all|commitment|decision|summary|transcript)$"),
    db: Session = Depends(get_db),
):
    """Search with GET method for easier linking and filtering."""
    try:
        return await memory_service.search_memory(
            db=db,
            query=q,
            limit=limit,
            similarity_threshold=similarity_threshold,
            meeting_id=meeting_id,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Memory search failed: {str(exc)}",
        ) from exc


# ---------------------------------------------------------
# Index Meeting
# ---------------------------------------------------------

@router.post(
    "/index/{meeting_id}",
)
async def index_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):

    from sqlalchemy import select

    from app.models.commitment import Commitment
    from app.models.decision import Decision
    from app.models.meeting import Meeting

    meeting = db.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id
        )
    )

    if meeting is None:
        raise HTTPException(
            status_code=404,
            detail="Meeting not found.",
        )

    decisions = list(
        db.scalars(
            select(Decision).where(
                Decision.meeting_id
                == meeting_id
            )
        ).all()
    )

    commitments = list(
        db.scalars(
            select(Commitment).where(
                Commitment.meeting_id
                == meeting_id
            )
        ).all()
    )

    decision_data = [
        {
            "title": decision.title,
            "description": decision.description,
        }
        for decision in decisions
    ]

    commitment_data = [
        {
            "task": commitment.task,
            "owner": commitment.owner_id,
            "deadline": (
                commitment.deadline.isoformat()
                if commitment.deadline
                else None
            ),
        }
        for commitment in commitments
    ]

    contents = memory_service.build_memory_content(
        summary=meeting.summary,
        decisions=decision_data,
        commitments=commitment_data,
    )

    if not contents:
        raise HTTPException(
            status_code=400,
            detail=(
                "No meeting information is available "
                "to index."
            ),
        )

    try:
        count = await memory_service.index_meeting(
            db=db,
            meeting_id=meeting_id,
            contents=contents,
        )

        return {
            "success": True,
            "meeting_id": str(meeting_id),
            "indexed_items": count,
        }

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "Memory indexing failed: "
                f"{str(exc)}"
            ),
        ) from exc