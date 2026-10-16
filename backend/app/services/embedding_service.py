
import os
from typing import Sequence
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.embedding import MeetingEmbedding


class EmbeddingService:
    """Create and search meeting embeddings using local Ollama."""

    def __init__(self) -> None:
        self.base_url = os.getenv(
            "OLLAMA_BASE_URL",
            "http://127.0.0.1:11434",
        ).rstrip("/")
        self.model = os.getenv(
            "OLLAMA_EMBEDDING_MODEL",
            "nomic-embed-text",
        )
        self.timeout = 120.0

    def is_available(self) -> bool:
        """Return whether the local Ollama service is reachable."""
        try:
            response = httpx.get(
                f"{self.base_url}/api/tags",
                timeout=5.0,
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False

    async def create_embedding(self, text: str) -> list[float]:
        """Generate a 768-dimensional vector using Ollama."""
        if not text or not text.strip():
            raise ValueError("Cannot create an embedding from empty text.")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={
                    "model": self.model,
                    "input": text,
                },
            )
            response.raise_for_status()
            data = response.json()

        embeddings = data.get("embeddings", [])
        if not embeddings:
            raise RuntimeError("Ollama returned no embeddings.")

        vector = embeddings[0]

        if len(vector) != 768:
            raise RuntimeError(
                f"Expected 768 embedding dimensions, got {len(vector)}."
            )

        return vector

    async def store_embedding(
        self,
        db: Session,
        meeting_id: UUID,
        content: str,
    ) -> MeetingEmbedding:
        """Generate and store one meeting-memory embedding."""
        vector = await self.create_embedding(content)

        record = MeetingEmbedding(
            meeting_id=meeting_id,
            content=content,
            embedding=vector,
        )

        try:
            db.add(record)
            db.commit()
            db.refresh(record)
            return record
        except Exception:
            db.rollback()
            raise

    async def store_embeddings(
        self,
        db: Session,
        meeting_id: UUID,
        contents: Sequence[str],
    ) -> list[MeetingEmbedding]:
        """Generate and store multiple meeting-memory embeddings."""
        records = []

        try:
            for content in contents:
                if not content or not content.strip():
                    continue

                vector = await self.create_embedding(content)

                record = MeetingEmbedding(
                    meeting_id=meeting_id,
                    content=content,
                    embedding=vector,
                )
                db.add(record)
                records.append(record)

            db.commit()

            for record in records:
                db.refresh(record)

            return records

        except Exception:
            db.rollback()
            raise

    async def search(
        self,
        db: Session,
        query: str,
        limit: int = 10,
        similarity_threshold: float = 0.70,
        meeting_id: UUID | None = None,
    ) -> list[tuple[MeetingEmbedding, float]]:
        """Find semantically similar meeting memories."""
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty.")

        if limit < 1:
            raise ValueError("Search limit must be at least 1.")

        query_vector = await self.create_embedding(query)

        distance = MeetingEmbedding.embedding.cosine_distance(
            query_vector
        )
        similarity = 1 - distance

        statement = (
            select(
                MeetingEmbedding,
                similarity.label("similarity"),
            )
            .where(similarity >= similarity_threshold)
        )

        if meeting_id is not None:
            statement = statement.where(
                MeetingEmbedding.meeting_id == meeting_id
            )

        statement = statement.order_by(distance).limit(limit)

        rows = db.execute(statement).all()

        return [
            (record, float(score))
            for record, score in rows
        ]


embedding_service = EmbeddingService()
