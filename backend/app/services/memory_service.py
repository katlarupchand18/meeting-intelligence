
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.embedding import MeetingEmbedding
from app.schemas.memory import MemorySearchResponse, MemorySearchResult
from app.services.embedding_service import embedding_service


class MemoryService:
    """Manage meeting memory indexing and semantic search."""

    async def index_meeting(
        self,
        db: Session,
        meeting_id: UUID,
        contents: list[str],
    ) -> int:
        cleaned_contents = list(
            dict.fromkeys(
                content.strip()
                for content in contents
                if content and content.strip()
            )
        )

        try:
            # Replace existing memory entries for this meeting.
            db.query(MeetingEmbedding).filter(
                MeetingEmbedding.meeting_id == meeting_id
            ).delete(synchronize_session=False)

            if not cleaned_contents:
                db.commit()
                return 0

            records = await embedding_service.store_embeddings(
                db=db,
                meeting_id=meeting_id,
                contents=cleaned_contents,
            )

            return len(records)

        except Exception:
            db.rollback()
            raise

    async def search_memory(
        self,
        db: Session,
        query: str,
        limit: int = 10,
        similarity_threshold: float = 0.35,
        meeting_id: UUID | None = None,
    ) -> MemorySearchResponse:
        rows = await embedding_service.search(
            db=db,
            query=query,
            limit=limit,
            similarity_threshold=similarity_threshold,
            meeting_id=meeting_id,
        )

        results = [
            MemorySearchResult(
                meeting_id=record.meeting_id,
                content=record.content,
                similarity=round(similarity, 4),
            )
            for record, similarity in rows
        ]

        return MemorySearchResponse(
            query=query,
            results=results,
            total=len(results),
        )

    def build_memory_content(
        self,
        summary: str | None,
        decisions: list[dict],
        commitments: list[dict],
    ) -> list[str]:
        contents = []

        if summary:
            contents.append(f"Meeting summary: {summary}")

        for decision in decisions:
            title = decision.get("title", "")
            description = decision.get("description", "")

            if title or description:
                contents.append(
                    f"Decision: {title}. {description}".strip()
                )

        for commitment in commitments:
            task = commitment.get("task", "")
            owner = commitment.get("owner") or "unassigned"
            deadline = commitment.get("deadline") or "no deadline"

            if task:
                contents.append(
                    f"Commitment: {task}. "
                    f"Owner: {owner}. "
                    f"Deadline: {deadline}."
                )

        return list(dict.fromkeys(contents))


memory_service = MemoryService()
