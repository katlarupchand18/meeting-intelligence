"""
Hybrid Meeting Analysis Service.

Pipeline:
Transcript input
→ NLP preprocessing
→ Sentence and speaker identification
→ Entity and deadline extraction
→ NLP-based commitment candidate detection
→ NLP-based decision candidate detection
→ Semantic embeddings and candidate matching
→ Groq/Ollama contextual validation
→ Structured schema validation
→ Evidence linking
→ Deduplication
→ Database persistence
→ Human verification
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.commitment import (
    Commitment,
    CommitmentStatus,
    CommitmentStrength,
)
from app.models.decision import (
    Decision,
    DecisionStatus,
)
from app.models.embedding import MeetingEmbedding
from app.models.evidence import Evidence
from app.models.meeting import Meeting
from app.models.transcript import TranscriptSegment

from app.schemas.analysis import MeetingAnalysisResponse

from app.services.llm_service import llm_service
from app.services.nlp_preprocessing_service import (
    nlp_preprocessing_service,
    ProcessedTranscript,
)
from app.services.nlp_commitment_extraction import (
    nlp_commitment_extractor,
    CommitmentCandidate,
)
from app.services.nlp_decision_extraction import (
    nlp_decision_extractor,
    DecisionCandidate,
)
from app.services.owner_resolution_service import (
    owner_resolution_service,
)
from app.services.embedding_service import embedding_service
from app.services.memory_service import memory_service

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Main meeting intelligence service with hybrid NLP + LLM pipeline.
    """

    # Chunk size for large transcripts (number of segments per chunk)
    CHUNK_SIZE = 20

    # Maximum candidates to send for LLM validation per chunk
    MAX_CANDIDATES_PER_CHUNK = 15

    async def analyze_meeting(
        self,
        db: Session,
        meeting_id: UUID,
    ) -> MeetingAnalysisResponse:
        """
        Analyze a meeting using the hybrid NLP + LLM pipeline.

        Args:
            db: Database session
            meeting_id: Meeting UUID

        Returns:
            MeetingAnalysisResponse with extracted decisions, commitments, evidence
        """
        meeting = db.scalar(
            select(Meeting).where(Meeting.id == meeting_id)
        )

        if meeting is None:
            raise ValueError("Meeting not found.")

        # -----------------------------------------------------
        # LOAD TRANSCRIPT
        # -----------------------------------------------------
        transcript_segments = list(
            db.scalars(
                select(TranscriptSegment)
                .where(TranscriptSegment.meeting_id == meeting_id)
                .order_by(TranscriptSegment.sequence_number)
            ).all()
        )

        if not transcript_segments:
            raise ValueError(
                "No transcript found for this meeting. "
                "Transcribe the meeting before analysis."
            )

        # Convert segments to dict format for NLP processing
        segments_data = [
            {
                "id": seg.id,
                "speaker_name": seg.speaker_name,
                "speaker_label": seg.speaker_label,
                "text": seg.text,
                "start_time": seg.start_time,
                "end_time": seg.end_time,
                "sequence_number": seg.sequence_number,
            }
            for seg in transcript_segments
        ]

        # -----------------------------------------------------
        # NLP PREPROCESSING
        # -----------------------------------------------------
        logger.info(f"Starting NLP preprocessing for meeting {meeting_id}")
        processed = nlp_preprocessing_service.process_transcript(
            meeting_id=meeting_id,
            segments=segments_data,
        )
        logger.info(
            f"NLP preprocessing complete: {len(processed.sentences)} sentences, "
            f"{len(processed.entities)} entities, {len(processed.dates)} dates, "
            f"{len(processed.speakers)} speakers"
        )

        # -----------------------------------------------------
        # NLP-BASED CANDIDATE EXTRACTION
        # -----------------------------------------------------
        logger.info("Extracting commitment candidates via NLP...")
        commitment_candidates = nlp_commitment_extractor.extract_candidates(processed)
        logger.info(f"Found {len(commitment_candidates)} commitment candidates")

        logger.info("Extracting decision candidates via NLP...")
        decision_candidates = nlp_decision_extractor.extract_candidates(processed)
        logger.info(f"Found {len(decision_candidates)} decision candidates")

        # -----------------------------------------------------
        # LLM CONTEXTUAL VALIDATION
        # -----------------------------------------------------
        logger.info("Running LLM contextual validation...")

        # Process in chunks for large transcripts
        if len(processed.sentences) > self.CHUNK_SIZE:
            validated_commitments, validated_decisions = await self._validate_in_chunks(
                processed, commitment_candidates, decision_candidates
            )
        else:
            validated_commitments, validated_decisions = await self._validate_candidates(
                processed, commitment_candidates, decision_candidates
            )

        logger.info(
            f"Validation complete: {len(validated_commitments)} commitments, "
            f"{len(validated_decisions)} decisions"
        )

        # -----------------------------------------------------
        # DELETE PREVIOUS AI RESULTS
        # -----------------------------------------------------
        self._delete_previous_results(db, meeting_id)

        # -----------------------------------------------------
        # SAVE DECISIONS
        # -----------------------------------------------------
        saved_decisions: list[tuple[Decision, dict[str, Any]]] = []

        for decision_data in validated_decisions:
            decision = self._create_decision(meeting_id, decision_data)
            db.add(decision)
            db.flush()
            saved_decisions.append((decision, decision_data))

        # -----------------------------------------------------
        # SAVE COMMITMENTS
        # -----------------------------------------------------
        saved_commitments: list[tuple[Commitment, dict[str, Any]]] = []

        for commitment_data in validated_commitments:
            commitment = self._create_commitment(meeting_id, commitment_data)
            db.add(commitment)
            db.flush()
            saved_commitments.append((commitment, commitment_data))

        # -----------------------------------------------------
        # RESOLVE COMMITMENT OWNERS
        # -----------------------------------------------------
        db.flush()

        assigned_owner_count = owner_resolution_service.resolve_meeting_commitments(
            db=db, meeting_id=meeting_id
        )
        logger.info(
            f"Commitment owner resolution: {assigned_owner_count}/{len(saved_commitments)} assigned."
        )

        # -----------------------------------------------------
        # SAVE EVIDENCE
        # -----------------------------------------------------
        saved_evidence: list[Evidence] = []

        self._create_decision_evidence(
            db=db,
            meeting_id=meeting_id,
            decisions=saved_decisions,
            transcript_segments=transcript_segments,
            output=saved_evidence,
        )

        self._create_commitment_evidence(
            db=db,
            meeting_id=meeting_id,
            commitments=saved_commitments,
            transcript_segments=transcript_segments,
            output=saved_evidence,
        )

        # -----------------------------------------------------
        # GENERATE SUMMARY AND KEY TOPICS
        # -----------------------------------------------------
        summary, key_topics = await self._generate_summary_and_topics(
            processed, validated_commitments, validated_decisions
        )

        if summary:
            meeting.summary = summary

        db.commit()

        # -----------------------------------------------------
        # INDEX FOR MEMORY SEARCH
        # -----------------------------------------------------
        try:
            memory_contents = memory_service.build_memory_content(
                summary=summary,
                decisions=[d[1] for d in saved_decisions],
                commitments=[c[1] for c in saved_commitments],
            )
            if memory_contents:
                await memory_service.index_meeting(db, meeting_id, memory_contents)
        except Exception as e:
            logger.warning(f"Failed to index meeting for memory search: {e}")

        # -----------------------------------------------------
        # REFRESH
        # -----------------------------------------------------
        for decision, _ in saved_decisions:
            db.refresh(decision)
        for commitment, _ in saved_commitments:
            db.refresh(commitment)
        for evidence in saved_evidence:
            db.refresh(evidence)
        db.refresh(meeting)

        # -----------------------------------------------------
        # CONFIDENCE
        # -----------------------------------------------------
        overall_confidence = self._calculate_overall_confidence(
            decisions=[d for d, _ in saved_decisions],
            commitments=[c for c, _ in saved_commitments],
            evidence=saved_evidence,
        )

        # -----------------------------------------------------
        # RESPONSE
        # -----------------------------------------------------
        return MeetingAnalysisResponse(
            meeting_id=meeting_id,
            summary=summary,
            key_topics=key_topics,
            decisions=[
                self._decision_to_dict(decision)
                for decision, _ in saved_decisions
            ],
            commitments=[
                self._commitment_to_dict(commitment)
                for commitment, _ in saved_commitments
            ],
            evidence=[
                self._evidence_to_dict(evidence)
                for evidence in saved_evidence
            ],
            overall_confidence=overall_confidence,
            processing_status="completed",
        )

    # =========================================================
    # LLM VALIDATION
    # =========================================================

    async def _validate_in_chunks(
        self,
        processed: ProcessedTranscript,
        commitment_candidates: list[CommitmentCandidate],
        decision_candidates: list[DecisionCandidate],
    ) -> tuple[list[dict], list[dict]]:
        """Validate candidates in chunks for large transcripts."""
        # Group candidates by sentence index ranges
        sentences_per_chunk = self.CHUNK_SIZE
        num_chunks = (len(processed.sentences) + sentences_per_chunk - 1) // sentences_per_chunk

        all_validated_commitments = []
        all_validated_decisions = []

        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * sentences_per_chunk
            end_idx = min(start_idx + sentences_per_chunk, len(processed.sentences))

            # Filter candidates for this chunk
            chunk_commitments = [
                c for c in commitment_candidates
                if self._get_candidate_sentence_idx(c, processed) in range(start_idx, end_idx)
            ]
            chunk_decisions = [
                d for d in decision_candidates
                if self._get_candidate_sentence_idx(d, processed) in range(start_idx, end_idx)
            ]

            if chunk_commitments or chunk_decisions:
                validated_c, validated_d = await self._validate_candidates(
                    processed, chunk_commitments, chunk_decisions, start_idx, end_idx
                )
                all_validated_commitments.extend(validated_c)
                all_validated_decisions.extend(validated_d)

        # Deduplicate across chunks
        all_validated_commitments = self._deduplicate_commitments(all_validated_commitments)
        all_validated_decisions = self._deduplicate_decisions(all_validated_decisions)

        return all_validated_commitments, all_validated_decisions

    def _get_candidate_sentence_idx(
        self,
        candidate: CommitmentCandidate | DecisionCandidate,
        processed: ProcessedTranscript,
    ) -> int:
        """Find the sentence index for a candidate."""
        for i, sent in enumerate(processed.sentences):
            if sent.text == candidate.source_sentence:
                return i
        return 0

    async def _validate_candidates(
        self,
        processed: ProcessedTranscript,
        commitment_candidates: list[CommitmentCandidate],
        decision_candidates: list[DecisionCandidate],
        start_idx: int = 0,
        end_idx: int | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """
        Send NLP-extracted candidates to LLM for contextual validation.

        This is the key hybrid step: NLP does candidate extraction,
        LLM validates and resolves ambiguities.
        """
        if not commitment_candidates and not decision_candidates:
            return [], []

        # Limit candidates per call
        commitment_candidates = commitment_candidates[:self.MAX_CANDIDATES_PER_CHUNK]
        decision_candidates = decision_candidates[:self.MAX_CANDIDATES_PER_CHUNK]

        # Build context from relevant sentences
        context_sentences = processed.sentences[start_idx:end_idx]
        context_text = "\n".join(
            f"[{i}] {s.speaker or 'Speaker'}: {s.text}"
            for i, s in enumerate(context_sentences)
        )

        # Prepare candidates for LLM
        commitment_data = []
        for c in commitment_candidates:
            commitment_data.append({
                "task": c.task,
                "owner": c.owner,
                "deadline": c.deadline_text,
                "strength": c.strength,
                "confidence": c.confidence,
                "source_sentence": c.source_sentence,
                "speaker": c.speaker,
                "evidence_tokens": c.evidence_tokens,
                "linguistic_features": c.linguistic_features,
                "candidate_score": c.candidate_score,
            })

        decision_data = []
        for d in decision_candidates:
            decision_data.append({
                "title": d.title,
                "description": d.description,
                "status": d.status,
                "confidence": d.confidence,
                "source_sentence": d.source_sentence,
                "speaker": d.speaker,
                "evidence_tokens": d.evidence_tokens,
                "linguistic_features": d.linguistic_features,
                "candidate_score": d.candidate_score,
            })

        validation_prompt = f"""
You are a meeting intelligence validation engine.

You receive NLP-extracted candidates for commitments and decisions from a meeting transcript.
Your job is to validate, refine, and filter these candidates using the full context.

TRANSCRIPT CONTEXT (relevant portion):
{context_text}

NLP-EXTRACTED COMMITMENT CANDIDATES:
{json.dumps(commitment_data, indent=2)}

NLP-EXTRACTED DECISION CANDIDATES:
{json.dumps(decision_data, indent=2)}

VALIDATION RULES:

1. COMMITMENTS:
   - Must have a clear action/task someone is expected to perform
   - Distinguish: firm commitments (will/shall/must), weak (should/plan), requests (can you/please), unassigned
   - Owner must be explicitly mentioned or clearly implied by speaker
   - Deadline must be explicitly stated, not inferred
   - Reject: group activities, delegations, approvals, future events without individual action
   - Reject: negated statements ("I won't do X")

2. DECISIONS:
   - Must be a clear group decision, not a proposal or discussion
   - Status: accepted (approved/adopted/agreed), rejected, proposed, changed, superseded
   - Reject: "maybe we should", "I think we should", "someone suggested"
   - Keep: "motion carried", "we approve", "it is decided", "resolved"

3. EVIDENCE:
   - Must use exact wording from transcript
   - Include speaker attribution

Return ONLY valid JSON:

{{
  "commitments": [
    {{
      "task": "specific action",
      "owner": "person name or null",
      "deadline": "deadline text or null",
      "deadline_text": "original wording or null",
      "strength": "firm|weak|request|unassigned",
      "confidence": 0.0,
      "evidence": "exact transcript wording"
    }}
  ],
  "decisions": [
    {{
      "title": "short title",
      "description": "what was decided",
      "status": "accepted|rejected|proposed|changed|superseded",
      "confidence": 0.0,
      "evidence": "exact transcript wording"
    }}
  ]
}}

Allowed commitment strengths: firm, weak, request, unassigned
Allowed decision statuses: accepted, rejected, proposed, changed, superseded
"""

        try:
            result = await llm_service.agenerate_json(
                prompt=validation_prompt,
                system_prompt=(
                    "You are a strict meeting intelligence validation engine. "
                    "Return only valid JSON. Be conservative - prefer missing "
                    "information over false positives."
                ),
            )

            validated_commitments = result.get("commitments", [])
            validated_decisions = result.get("decisions", [])

            # Normalize
            validated_commitments = self._normalize_validated_commitments(validated_commitments)
            validated_decisions = self._normalize_validated_decisions(validated_decisions)

            return validated_commitments, validated_decisions

        except Exception as exc:
            logger.warning(f"LLM validation failed, using NLP candidates: {exc}")
            # Fallback: use NLP candidates directly
            fallback_commitments = [
                {
                    "task": c.task,
                    "owner": c.owner,
                    "deadline": c.deadline,
                    "deadline_text": c.deadline_text,
                    "strength": c.strength,
                    "confidence": c.confidence,
                    "evidence": c.source_sentence,
                }
                for c in commitment_candidates
            ]
            fallback_decisions = [
                {
                    "title": d.title,
                    "description": d.description,
                    "status": d.status,
                    "confidence": d.confidence,
                    "evidence": d.source_sentence,
                }
                for d in decision_candidates
            ]
            return fallback_commitments, fallback_decisions

    def _normalize_validated_commitments(
        self,
        commitments: list[dict],
    ) -> list[dict]:
        """Normalize validated commitments."""
        normalized = []
        for item in commitments:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "task": str(item.get("task", "")).strip() or "Untitled commitment",
                "owner": str(item.get("owner", "")).strip() or None,
                "deadline": str(item.get("deadline", "")).strip() or None,
                "deadline_text": str(item.get("deadline_text", "")).strip() or None,
                "strength": str(item.get("strength", "unassigned")).lower().strip(),
                "confidence": self._safe_confidence(item.get("confidence"), 0.0),
                "evidence": str(item.get("evidence", "")).strip(),
            })
        return normalized

    def _normalize_validated_decisions(
        self,
        decisions: list[dict],
    ) -> list[dict]:
        """Normalize validated decisions."""
        normalized = []
        for item in decisions:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "title": str(item.get("title", "")).strip() or "Untitled decision",
                "description": str(item.get("description", "")).strip() or "No description available.",
                "status": str(item.get("status", "accepted")).lower().strip(),
                "confidence": self._safe_confidence(item.get("confidence"), 0.0),
                "evidence": str(item.get("evidence", "")).strip(),
            })
        return normalized

    async def _generate_summary_and_topics(
        self,
        processed: ProcessedTranscript,
        commitments: list[dict],
        decisions: list[dict],
    ) -> tuple[str | None, list[str]]:
        """Generate meeting summary and key topics using LLM."""
        # Build transcript excerpt
        transcript_text = "\n".join(
            f"{s.speaker or 'Speaker'}: {s.text}"
            for s in processed.sentences[:100]  # Limit for context
        )

        prompt = f"""
Generate a concise meeting summary and key topics.

TRANSCRIPT:
{transcript_text}

EXTRACTED COMMITMENTS: {len(commitments)}
EXTRACTED DECISIONS: {len(decisions)}

Return ONLY JSON:
{{
  "summary": "concise 2-3 sentence summary",
  "key_topics": ["topic1", "topic2", "topic3"]
}}
"""

        try:
            result = await llm_service.agenerate_json(
                prompt=prompt,
                system_prompt="Generate concise meeting summaries. Return only valid JSON.",
            )
            summary = result.get("summary", "").strip() or None
            key_topics = result.get("key_topics", [])
            if not isinstance(key_topics, list):
                key_topics = []
            return summary, [str(t).strip() for t in key_topics if t]
        except Exception as e:
            logger.warning(f"Summary generation failed: {e}")
            # Fallback: extract from NLP
            topics = set()
            for ent in processed.entities:
                if ent.label in ("ORG", "PRODUCT", "EVENT", "WORK_OF_ART"):
                    topics.add(ent.text)
            return None, list(topics)[:10]

    # =========================================================
    # CREATE DECISION
    # =========================================================

    def _create_decision(
        self,
        meeting_id: UUID,
        data: dict[str, Any],
    ) -> Decision:
        status = self._map_decision_status(data.get("status"))
        confidence = self._safe_confidence(data.get("confidence"), 0.0)
        title = self._clean_string(data.get("title")) or "Untitled decision"
        description = self._clean_string(data.get("description")) or "No description available."

        return Decision(
            meeting_id=meeting_id,
            title=title,
            description=description,
            status=status,
            confidence=confidence,
        )

    # =========================================================
    # CREATE COMMITMENT
    # =========================================================

    def _create_commitment(
        self,
        meeting_id: UUID,
        data: dict[str, Any],
    ) -> Commitment:
        strength = self._map_commitment_strength(data.get("strength"))
        confidence = self._safe_confidence(data.get("confidence"), 0.0)
        task = self._clean_string(data.get("task")) or "Untitled commitment"
        owner = self._clean_string(data.get("owner"))
        deadline_text = self._clean_string(data.get("deadline_text") or data.get("deadline"))

        notes = None
        if owner:
            notes = f"Owner identified by AI: {owner}"

        return Commitment(
            meeting_id=meeting_id,
            owner_id=None,  # Will be resolved by owner_resolution_service
            task=task,
            deadline=None,  # Parsed separately if needed
            deadline_text=deadline_text,
            strength=strength,
            status=CommitmentStatus.OPEN,
            confidence=confidence,
            notes=notes,
        )

    # =========================================================
    # EVIDENCE LINKING
    # =========================================================

    def _create_decision_evidence(
        self,
        db: Session,
        meeting_id: UUID,
        decisions: list[tuple[Decision, dict[str, Any]]],
        transcript_segments: list[TranscriptSegment],
        output: list[Evidence],
    ) -> None:
        for decision, data in decisions:
            evidence_text = self._clean_string(data.get("evidence"))
            if not evidence_text:
                evidence_text = decision.description

            segment = self._find_best_evidence_segment(
                evidence_text, transcript_segments
            )

            if segment is None:
                continue

            evidence = Evidence(
                meeting_id=meeting_id,
                transcript_segment_id=segment.id,
                decision_id=decision.id,
                commitment_id=None,
                evidence_type="decision",
                snippet=self._make_snippet(segment.text),
                confidence=decision.confidence,
            )

            db.add(evidence)
            output.append(evidence)

    def _create_commitment_evidence(
        self,
        db: Session,
        meeting_id: UUID,
        commitments: list[tuple[Commitment, dict[str, Any]]],
        transcript_segments: list[TranscriptSegment],
        output: list[Evidence],
    ) -> None:
        for commitment, data in commitments:
            evidence_text = self._clean_string(data.get("evidence"))
            if not evidence_text:
                evidence_text = commitment.task

            segment = self._find_best_evidence_segment(
                evidence_text, transcript_segments
            )

            if segment is None:
                continue

            evidence = Evidence(
                meeting_id=meeting_id,
                transcript_segment_id=segment.id,
                decision_id=None,
                commitment_id=commitment.id,
                evidence_type="commitment",
                snippet=self._make_snippet(segment.text),
                confidence=commitment.confidence,
            )

            db.add(evidence)
            output.append(evidence)

    def _find_best_evidence_segment(
        self,
        evidence_text: str,
        transcript_segments: list[TranscriptSegment],
    ) -> TranscriptSegment | None:
        if not transcript_segments:
            return None

        evidence_tokens = set(self._tokenize(evidence_text))
        if not evidence_tokens:
            return None

        best_segment = None
        best_score = 0.0

        for segment in transcript_segments:
            segment_tokens = set(self._tokenize(segment.text))
            if not segment_tokens:
                continue

            overlap = len(evidence_tokens & segment_tokens) / len(evidence_tokens)
            if overlap > best_score:
                best_score = overlap
                best_segment = segment

        if best_score < 0.10:
            return None

        return best_segment

    # =========================================================
    # DELETE OLD RESULTS
    # =========================================================

    def _delete_previous_results(
        self,
        db: Session,
        meeting_id: UUID,
    ) -> None:
        db.execute(
            delete(Evidence).where(Evidence.meeting_id == meeting_id)
        )
        db.execute(
            delete(Commitment).where(Commitment.meeting_id == meeting_id)
        )
        db.execute(
            delete(Decision).where(Decision.meeting_id == meeting_id)
        )
        db.execute(
            delete(MeetingEmbedding).where(MeetingEmbedding.meeting_id == meeting_id)
        )
        db.flush()

    # =========================================================
    # DEDUPLICATION
    # =========================================================

    def _deduplicate_commitments(
        self,
        commitments: list[dict],
    ) -> list[dict]:
        result = []
        seen = set()

        for item in commitments:
            key_fields = [
                self._clean_string(item.get("task")).lower(),
                self._clean_string(item.get("owner")).lower(),
            ]
            key = "|".join(key_fields)
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item)

        return result

    def _deduplicate_decisions(
        self,
        decisions: list[dict],
    ) -> list[dict]:
        result = []
        seen = set()

        for item in decisions:
            key_fields = [
                self._clean_string(item.get("title")).lower(),
                self._clean_string(item.get("description")).lower(),
            ]
            key = "|".join(key_fields)
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item)

        return result

    # =========================================================
    # CONFIDENCE
    # =========================================================

    @staticmethod
    def _safe_confidence(value: Any, default: float = 0.0) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return default
        return max(0.0, min(1.0, confidence))

    def _calculate_overall_confidence(
        self,
        decisions: list[Decision],
        commitments: list[Commitment],
        evidence: list[Evidence],
    ) -> float:
        values: list[float] = []

        for decision in decisions:
            values.append(self._safe_confidence(decision.confidence))
        for commitment in commitments:
            values.append(self._safe_confidence(commitment.confidence))
        for evidence_item in evidence:
            values.append(self._safe_confidence(evidence_item.confidence))

        if not values:
            return 0.0

        return round(sum(values) / len(values), 4)

    # =========================================================
    # SERIALIZATION
    # =========================================================

    @staticmethod
    def _decision_to_dict(decision: Decision) -> dict[str, Any]:
        return {
            "id": str(decision.id),
            "meeting_id": str(decision.meeting_id),
            "title": decision.title,
            "description": decision.description,
            "status": decision.status.value,
            "confidence": decision.confidence,
            "changed_from_decision_id": (
                str(decision.changed_from_decision_id)
                if decision.changed_from_decision_id else None
            ),
            "created_at": (
                decision.created_at.isoformat() if decision.created_at else None
            ),
        }

    @staticmethod
    def _commitment_to_dict(commitment: Commitment) -> dict[str, Any]:
        return {
            "id": str(commitment.id),
            "meeting_id": str(commitment.meeting_id),
            "owner_id": (
                str(commitment.owner_id) if commitment.owner_id else None
            ),
            "task": commitment.task,
            "deadline": (
                commitment.deadline.isoformat() if commitment.deadline else None
            ),
            "deadline_text": commitment.deadline_text,
            "strength": commitment.strength.value,
            "status": commitment.status.value,
            "confidence": commitment.confidence,
            "notes": commitment.notes,
            "created_at": (
                commitment.created_at.isoformat() if commitment.created_at else None
            ),
            "updated_at": (
                commitment.updated_at.isoformat() if commitment.updated_at else None
            ),
        }

    @staticmethod
    def _evidence_to_dict(evidence: Evidence) -> dict[str, Any]:
        return {
            "id": str(evidence.id),
            "meeting_id": str(evidence.meeting_id),
            "transcript_segment_id": (
                str(evidence.transcript_segment_id)
                if evidence.transcript_segment_id else None
            ),
            "commitment_id": (
                str(evidence.commitment_id) if evidence.commitment_id else None
            ),
            "decision_id": (
                str(evidence.decision_id) if evidence.decision_id else None
            ),
            "evidence_type": evidence.evidence_type,
            "snippet": evidence.snippet,
            "confidence": evidence.confidence,
            "created_at": (
                evidence.created_at.isoformat() if evidence.created_at else None
            ),
        }

    # =========================================================
    # TEXT HELPERS
    # =========================================================

    @staticmethod
    def _clean_string(value: Any) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        return value.strip()

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        if not text:
            return []
        import re
        return re.findall(r"[a-zA-Z0-9]+", text.lower())

    @staticmethod
    def _make_snippet(text: str, max_length: int = 500) -> str:
        text = text.strip()
        if len(text) <= max_length:
            return text
        return text[:max_length - 3].rstrip() + "..."

    @staticmethod
    def _map_decision_status(value: Any) -> DecisionStatus:
        normalized = str(value or "accepted").lower().strip()
        mapping = {
            "proposed": DecisionStatus.PROPOSED,
            "accepted": DecisionStatus.ACCEPTED,
            "rejected": DecisionStatus.REJECTED,
            "changed": DecisionStatus.CHANGED,
            "superseded": DecisionStatus.SUPERSEDED,
        }
        return mapping.get(normalized, DecisionStatus.ACCEPTED)

    @staticmethod
    def _map_commitment_strength(value: Any) -> CommitmentStrength:
        normalized = str(value or "unassigned").lower().strip()
        mapping = {
            "firm": CommitmentStrength.FIRM,
            "weak": CommitmentStrength.WEAK,
            "request": CommitmentStrength.REQUEST,
            "unassigned": CommitmentStrength.UNASSIGNED,
        }
        return mapping.get(normalized, CommitmentStrength.UNASSIGNED)


analysis_service = AnalysisService()