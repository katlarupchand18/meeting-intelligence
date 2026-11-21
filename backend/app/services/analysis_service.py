from __future__ import annotations
import asyncio

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.commitment import (
    Commitment,
    CommitmentStatus,
    CommitmentStrength,
)
from app.models.decision import (
    Decision,
    DecisionStatus,
)
from app.models.evidence import Evidence
from app.models.meeting import Meeting
from app.models.transcript import TranscriptSegment

from app.schemas.analysis import MeetingAnalysisResponse

from app.services.llm_service import llm_service
from app.services.owner_resolution_service import (
    owner_resolution_service,
)


class AnalysisService:
    """
    Main meeting intelligence service.

    Pipeline:

        Transcript
            ↓
        Chunk transcript
            ↓
        Qwen3 / Local LLM
            ↓
        Extract decisions + commitments
            ↓
        Merge results
            ↓
        Save decisions
            ↓
        Save commitments
            ↓
        Resolve owners
            ↓
        Save evidence
            ↓
        Update meeting
            ↓
        Return analysis
    """

    CHUNK_SIZE = 10

    # =========================================================
    # MAIN ANALYSIS
    # =========================================================

    async def analyze_meeting(
        self,
        db: Session,
        meeting_id: UUID,
    ) -> MeetingAnalysisResponse:

        meeting = db.scalar(
            select(Meeting).where(
                Meeting.id == meeting_id
            )
        )

        if meeting is None:
            raise ValueError(
                "Meeting not found."
            )

        # -----------------------------------------------------
        # LOAD TRANSCRIPT
        # -----------------------------------------------------

        transcript_segments = list(
            db.scalars(
                select(TranscriptSegment)
                .where(
                    TranscriptSegment.meeting_id
                    == meeting_id
                )
                .order_by(
                    TranscriptSegment.sequence_number
                )
            ).all()
        )

        if not transcript_segments:
            raise ValueError(
                "No transcript found for this meeting. "
                "Transcribe the meeting before analysis."
            )

        # -----------------------------------------------------
        # BUILD CHUNKS
        # -----------------------------------------------------

        chunks = self._build_chunks(
            transcript_segments
        )

        if not chunks:
            raise RuntimeError(
                "Unable to create transcript chunks."
            )

        # -----------------------------------------------------
        # ANALYZE CHUNKS
        # -----------------------------------------------------

        chunk_results: list[
            dict[str, Any]
        ] = []

        for chunk_number, chunk in enumerate(
            chunks,
            start=1,
        ):
            try:
                result = await asyncio.to_thread(
                    self._analyze_chunk,
                    chunk=chunk,
                    chunk_number=chunk_number,
                    total_chunks=len(chunks),
                )

                if result:
                    chunk_results.append(
                        result
                    )

            except Exception as exc:
                print(
                    f"Chunk {chunk_number} analysis failed: "
                    f"{exc}"
                )

        if not chunk_results:
            raise RuntimeError(
                "The local LLM could not analyze "
                "any transcript chunks."
            )

        # -----------------------------------------------------
        # MERGE RESULTS
        # -----------------------------------------------------

        merged = await asyncio.to_thread(
            self._merge_results,
            chunk_results,
        )

        # -----------------------------------------------------
        # DELETE PREVIOUS AI RESULTS
        # -----------------------------------------------------

        self._delete_previous_results(
            db=db,
            meeting_id=meeting_id,
        )

        # -----------------------------------------------------
        # SAVE DECISIONS
        # -----------------------------------------------------

        saved_decisions: list[
            tuple[Decision, dict[str, Any]]
        ] = []

        for decision_data in merged.get(
            "decisions",
            [],
        ):
            decision = self._create_decision(
                meeting_id=meeting_id,
                data=decision_data,
            )

            db.add(decision)
            db.flush()

            saved_decisions.append(
                (
                    decision,
                    decision_data,
                )
            )

        # -----------------------------------------------------
        # SAVE COMMITMENTS
        # -----------------------------------------------------

        saved_commitments: list[
            tuple[Commitment, dict[str, Any]]
        ] = []

        for commitment_data in merged.get(
            "commitments",
            [],
        ):
            commitment = self._create_commitment(
                meeting_id=meeting_id,
                data=commitment_data,
            )

            db.add(commitment)
            db.flush()

            saved_commitments.append(
                (
                    commitment,
                    commitment_data,
                )
            )

        # -----------------------------------------------------
        # RESOLVE COMMITMENT OWNERS
        # -----------------------------------------------------

        db.flush()

        assigned_owner_count = (
            owner_resolution_service
            .resolve_meeting_commitments(
                db=db,
                meeting_id=meeting_id,
            )
        )

        print(
            "Commitment owner resolution: "
            f"{assigned_owner_count}/"
            f"{len(saved_commitments)} assigned."
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
        # UPDATE MEETING SUMMARY
        # -----------------------------------------------------

        summary = self._clean_string(
            merged.get("summary")
        )

        key_topics = self._clean_string_list(
            merged.get("key_topics")
        )

        if summary:
            meeting.summary = summary

        db.commit()

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

        overall_confidence = (
            self._calculate_overall_confidence(
                decisions=[
                    decision
                    for decision, _
                    in saved_decisions
                ],
                commitments=[
                    commitment
                    for commitment, _
                    in saved_commitments
                ],
                evidence=saved_evidence,
            )
        )

        # -----------------------------------------------------
        # RESPONSE
        # -----------------------------------------------------

        return MeetingAnalysisResponse(
            meeting_id=meeting_id,
            summary=summary,
            key_topics=key_topics,
            decisions=[
                self._decision_to_dict(
                    decision
                )
                for decision, _
                in saved_decisions
            ],
            commitments=[
                self._commitment_to_dict(
                    commitment
                )
                for commitment, _
                in saved_commitments
            ],
            evidence=[
                self._evidence_to_dict(
                    evidence
                )
                for evidence in saved_evidence
            ],
            overall_confidence=overall_confidence,
            processing_status="completed",
        )

    # =========================================================
    # CHUNKING
    # =========================================================

    def _build_chunks(
        self,
        segments: list[TranscriptSegment],
    ) -> list[
        list[TranscriptSegment]
    ]:

        chunks: list[
            list[TranscriptSegment]
        ] = []

        current_chunk: list[
            TranscriptSegment
        ] = []

        for segment in segments:
            current_chunk.append(
                segment
            )

            if (
                len(current_chunk)
                >= self.CHUNK_SIZE
            ):
                chunks.append(
                    current_chunk
                )

                current_chunk = []

        if current_chunk:
            chunks.append(
                current_chunk
            )

        return chunks

    # =========================================================
    # CHUNK ANALYSIS
    # =========================================================

    def _analyze_chunk(
        self,
        chunk: list[TranscriptSegment],
        chunk_number: int,
        total_chunks: int,
    ) -> dict[str, Any]:

        transcript_text = (
            self._format_chunk(chunk)
        )

        system_prompt = """
You are the meeting intelligence engine for an
evidence-backed meeting accountability system.

Your job is to extract ONLY information actually
supported by the transcript.

Important rules:

1. Discussion is NOT a decision.
2. A proposal is NOT automatically a decision.
3. A request is NOT automatically a commitment.
4. A group decision is NOT automatically a personal commitment.
5. A commitment needs an action/task that someone is
   actually expected to perform.
6. Do not invent owners.
7. Do not invent deadlines.
8. Do not invent facts.
9. If an owner is explicitly mentioned, include the
   person's name.
10. Evidence must use wording from the transcript.
11. Prefer missing information over guessing.
12. False commitments are worse than missing commitments.

Statement types:

DISCUSSION:
People are talking about an issue.

PROPOSAL:
Someone suggests something but it is not yet accepted.

DECISION:
The group clearly approves, rejects, adopts, authorizes,
confirms, resolves, or otherwise reaches a final decision.

COMMITMENT:
A person or clearly identified party is expected to perform
a specific action.

Examples:

"Maybe we should approve the proposal."
=> proposal, NOT decision.

"I think we should..."
=> discussion/proposal, NOT commitment.

"The motion is carried."
=> decision.

"I will send the report tomorrow."
=> commitment.

"Can you send the report?"
=> request unless the transcript clearly shows acceptance.

"The council will attend the conference."
=> usually a decision/delegation, NOT an individual commitment.

Return ONLY valid JSON.
"""

        prompt = f"""
Analyze transcript chunk {chunk_number}
of {total_chunks}.

TRANSCRIPT:

{transcript_text}

Return exactly this JSON structure:

{{
  "summary": "short summary of this chunk",
  "key_topics": [
    "topic 1",
    "topic 2"
  ],
  "decisions": [
    {{
      "title": "short decision title",
      "description": "what was actually decided",
      "status": "accepted",
      "confidence": 0.0,
      "evidence": "short exact transcript evidence"
    }}
  ],
  "commitments": [
    {{
      "task": "specific action",
      "owner": "person name or null",
      "deadline": "deadline text or null",
      "strength": "firm",
      "confidence": 0.0,
      "evidence": "short exact transcript evidence"
    }}
  ]
}}

Allowed decision status values:

accepted
rejected
proposed
changed
superseded

Allowed commitment strength values:

firm
weak
request
unassigned

Do not create a commitment merely because the transcript
contains a future event, meeting, delegation, approval,
resolution, or group activity.

If there are no decisions, return:

"decisions": []

If there are no commitments, return:

"commitments": []

Transcript:

{transcript_text}
"""

        result = llm_service.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
        )

        return self._normalize_chunk_result(
            result
        )

    # =========================================================
    # MERGE
    # =========================================================

    def _merge_results(
        self,
        chunk_results: list[
            dict[str, Any]
        ],
    ) -> dict[str, Any]:

        if len(chunk_results) == 1:
            return (
                self._normalize_merged_result(
                    chunk_results[0]
                )
            )

        summaries: list[str] = []
        topics: list[str] = []
        decisions: list[
            dict[str, Any]
        ] = []
        commitments: list[
            dict[str, Any]
        ] = []

        for result in chunk_results:

            summary = self._clean_string(
                result.get("summary")
            )

            if summary:
                summaries.append(
                    summary
                )

            topics.extend(
                self._clean_string_list(
                    result.get(
                        "key_topics"
                    )
                )
            )

            decisions.extend(
                result.get(
                    "decisions",
                    [],
                )
            )

            commitments.extend(
                result.get(
                    "commitments",
                    [],
                )
            )

        decisions = (
            self._deduplicate_items(
                decisions,
                [
                    "title",
                    "description",
                ],
            )
        )

        commitments = (
            self._deduplicate_items(
                commitments,
                [
                    "task",
                    "owner",
                ],
            )
        )

        topics = (
            self._deduplicate_strings(
                topics
            )
        )

        merge_prompt = f"""
You are merging structured analysis from multiple
chunks of the SAME meeting.

Your most important job is to avoid false commitments.

Rules:

1. Decision and commitment are different.
2. A decision may authorize something without creating
   an individual commitment.
3. Group activities, delegations, conference attendance,
   approvals and resolutions are generally decisions unless
   an individual action is clearly assigned.
4. Keep only real commitments.
5. Preserve explicit owners.
6. Never invent an owner.
7. Never invent a deadline.
8. Preserve confidence.
9. Combine duplicate decisions.
10. Combine duplicate commitments.
11. Keep evidence-supported information only.

CHUNK SUMMARIES:

{self._json_for_prompt(summaries)}

CANDIDATE DECISIONS:

{self._json_for_prompt(decisions)}

CANDIDATE COMMITMENTS:

{self._json_for_prompt(commitments)}

Return ONLY JSON:

{{
  "summary": "concise overall meeting summary",
  "key_topics": [
    "topic 1",
    "topic 2"
  ],
  "decisions": [
    {{
      "title": "short title",
      "description": "final decision",
      "status": "accepted",
      "confidence": 0.0,
      "evidence": "supporting transcript wording"
    }}
  ],
  "commitments": [
    {{
      "task": "specific action",
      "owner": "person or null",
      "deadline": "deadline or null",
      "strength": "firm",
      "confidence": 0.0,
      "evidence": "supporting transcript wording"
    }}
  ]
}}

Allowed decision statuses:

accepted
rejected
proposed
changed
superseded

Allowed commitment strengths:

firm
weak
request
unassigned
"""

        try:
            merged = (
                llm_service.generate_json(
                    prompt=merge_prompt,
                    system_prompt=(
                        "You are a strict meeting "
                        "intelligence merging engine. "
                        "Return only valid JSON."
                    ),
                )
            )

            normalized = (
                self._normalize_merged_result(
                    merged
                )
            )

            if (
                not normalized["decisions"]
                and decisions
            ):
                normalized["decisions"] = (
                    decisions
                )

            if (
                not normalized["commitments"]
                and commitments
            ):
                normalized[
                    "commitments"
                ] = commitments

            if not normalized[
                "key_topics"
            ]:
                normalized[
                    "key_topics"
                ] = topics

            if not normalized[
                "summary"
            ]:
                normalized[
                    "summary"
                ] = " ".join(
                    summaries
                )

            return normalized

        except Exception as exc:

            print(
                "Merge analysis failed, "
                f"using chunk results: {exc}"
            )

            return {
                "summary": " ".join(
                    summaries
                ),
                "key_topics": topics,
                "decisions": decisions,
                "commitments": commitments,
            }

    # =========================================================
    # CREATE DECISION
    # =========================================================

    def _create_decision(
        self,
        meeting_id: UUID,
        data: dict[str, Any],
    ) -> Decision:

        status = (
            self._map_decision_status(
                data.get("status")
            )
        )

        confidence = (
            self._safe_confidence(
                data.get(
                    "confidence"
                ),
                0.0,
            )
        )

        title = (
            self._clean_string(
                data.get("title")
            )
            or "Untitled decision"
        )

        description = (
            self._clean_string(
                data.get(
                    "description"
                )
            )
            or "No description available."
        )

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

        strength = (
            self._map_commitment_strength(
                data.get("strength")
            )
        )

        confidence = (
            self._safe_confidence(
                data.get(
                    "confidence"
                ),
                0.0,
            )
        )

        task = (
            self._clean_string(
                data.get("task")
            )
            or self._clean_string(
                data.get("title")
            )
            or "Untitled commitment"
        )

        owner = self._clean_string(
            data.get("owner")
        )

        deadline_text = (
            self._clean_string(
                data.get("deadline")
            )
        )

        notes = None

        if owner:
            notes = (
                "Owner identified by AI: "
                f"{owner}"
            )

        return Commitment(
            meeting_id=meeting_id,
            owner_id=None,
            task=task,
            deadline=None,
            deadline_text=deadline_text,
            strength=strength,
            status=CommitmentStatus.OPEN,
            confidence=confidence,
            notes=notes,
        )

    # =========================================================
    # DECISION EVIDENCE
    # =========================================================

    def _create_decision_evidence(
        self,
        db: Session,
        meeting_id: UUID,
        decisions: list[
            tuple[
                Decision,
                dict[str, Any],
            ]
        ],
        transcript_segments: list[
            TranscriptSegment
        ],
        output: list[Evidence],
    ) -> None:

        for decision, data in decisions:

            evidence_text = (
                self._clean_string(
                    data.get(
                        "evidence"
                    )
                )
            )

            if not evidence_text:
                evidence_text = (
                    decision.description
                )

            segment = (
                self._find_best_evidence_segment(
                    evidence_text,
                    transcript_segments,
                )
            )

            if segment is None:
                continue

            evidence = Evidence(
                meeting_id=meeting_id,
                transcript_segment_id=segment.id,
                decision_id=decision.id,
                commitment_id=None,
                evidence_type="decision",
                snippet=self._make_snippet(
                    segment.text
                ),
                confidence=decision.confidence,
            )

            db.add(evidence)
            output.append(evidence)

    # =========================================================
    # COMMITMENT EVIDENCE
    # =========================================================

    def _create_commitment_evidence(
        self,
        db: Session,
        meeting_id: UUID,
        commitments: list[
            tuple[
                Commitment,
                dict[str, Any],
            ]
        ],
        transcript_segments: list[
            TranscriptSegment
        ],
        output: list[Evidence],
    ) -> None:

        for commitment, data in commitments:

            evidence_text = (
                self._clean_string(
                    data.get(
                        "evidence"
                    )
                )
            )

            if not evidence_text:
                evidence_text = (
                    commitment.task
                )

            segment = (
                self._find_best_evidence_segment(
                    evidence_text,
                    transcript_segments,
                )
            )

            if segment is None:
                continue

            evidence = Evidence(
                meeting_id=meeting_id,
                transcript_segment_id=segment.id,
                decision_id=None,
                commitment_id=commitment.id,
                evidence_type="commitment",
                snippet=self._make_snippet(
                    segment.text
                ),
                confidence=commitment.confidence,
            )

            db.add(evidence)
            output.append(evidence)

    # =========================================================
    # FIND EVIDENCE
    # =========================================================

    def _find_best_evidence_segment(
        self,
        evidence_text: str,
        transcript_segments: list[
            TranscriptSegment
        ],
    ) -> (
        TranscriptSegment | None
    ):

        if not transcript_segments:
            return None

        evidence_tokens = set(
            self._tokenize(
                evidence_text
            )
        )

        if not evidence_tokens:
            return None

        best_segment = None
        best_score = 0.0

        for segment in transcript_segments:

            segment_tokens = set(
                self._tokenize(
                    segment.text
                )
            )

            if not segment_tokens:
                continue

            overlap = (
                len(
                    evidence_tokens
                    & segment_tokens
                )
                / len(evidence_tokens)
            )

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
            delete(Evidence).where(
                Evidence.meeting_id
                == meeting_id
            )
        )

        db.execute(
            delete(Commitment).where(
                Commitment.meeting_id
                == meeting_id
            )
        )

        db.execute(
            delete(Decision).where(
                Decision.meeting_id
                == meeting_id
            )
        )

        db.flush()

    # =========================================================
    # NORMALIZATION
    # =========================================================

    def _normalize_chunk_result(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:

        return {
            "summary": self._clean_string(
                result.get(
                    "summary"
                )
            ),
            "key_topics": (
                self._clean_string_list(
                    result.get(
                        "key_topics"
                    )
                )
            ),
            "decisions": (
                self._normalize_decisions(
                    result.get(
                        "decisions"
                    )
                )
            ),
            "commitments": (
                self._normalize_commitments(
                    result.get(
                        "commitments"
                    )
                )
            ),
        }

    def _normalize_merged_result(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:

        return {
            "summary": self._clean_string(
                result.get(
                    "summary"
                )
            ),
            "key_topics": (
                self._clean_string_list(
                    result.get(
                        "key_topics"
                    )
                )
            ),
            "decisions": (
                self._normalize_decisions(
                    result.get(
                        "decisions"
                    )
                )
            ),
            "commitments": (
                self._normalize_commitments(
                    result.get(
                        "commitments"
                    )
                )
            ),
        }

    # =========================================================
    # NORMALIZE DECISIONS
    # =========================================================

    def _normalize_decisions(
        self,
        decisions: Any,
    ) -> list[
        dict[str, Any]
    ]:

        if not isinstance(
            decisions,
            list,
        ):
            return []

        normalized = []

        for item in decisions:

            if not isinstance(
                item,
                dict,
            ):
                continue

            normalized.append(
                {
                    "title": (
                        self._clean_string(
                            item.get(
                                "title"
                            )
                        )
                        or "Untitled decision"
                    ),
                    "description": (
                        self._clean_string(
                            item.get(
                                "description"
                            )
                        )
                        or "No description available."
                    ),
                    "status": (
                        self._clean_string(
                            item.get(
                                "status"
                            )
                        )
                        or "accepted"
                    ).lower(),
                    "confidence": (
                        self._safe_confidence(
                            item.get(
                                "confidence"
                            ),
                            0.0,
                        )
                    ),
                    "evidence": (
                        self._clean_string(
                            item.get(
                                "evidence"
                            )
                        )
                    ),
                }
            )

        return normalized

    # =========================================================
    # NORMALIZE COMMITMENTS
    # =========================================================

    def _normalize_commitments(
        self,
        commitments: Any,
    ) -> list[
        dict[str, Any]
    ]:

        if not isinstance(
            commitments,
            list,
        ):
            return []

        normalized = []

        for item in commitments:

            if not isinstance(
                item,
                dict,
            ):
                continue

            normalized.append(
                {
                    "task": (
                        self._clean_string(
                            item.get(
                                "task"
                            )
                        )
                        or self._clean_string(
                            item.get(
                                "title"
                            )
                        )
                        or "Untitled commitment"
                    ),
                    "owner": (
                        self._clean_string(
                            item.get(
                                "owner"
                            )
                        )
                    ),
                    "deadline": (
                        self._clean_string(
                            item.get(
                                "deadline"
                            )
                        )
                    ),
                    "strength": (
                        self._clean_string(
                            item.get(
                                "strength"
                            )
                        )
                        or "unassigned"
                    ).lower(),
                    "confidence": (
                        self._safe_confidence(
                            item.get(
                                "confidence"
                            ),
                            0.0,
                        )
                    ),
                    "evidence": (
                        self._clean_string(
                            item.get(
                                "evidence"
                            )
                        )
                    ),
                }
            )

        return normalized

    # =========================================================
    # ENUM MAPPING
    # =========================================================

    @staticmethod
    def _map_decision_status(
        value: Any,
    ) -> DecisionStatus:

        normalized = str(
            value or "accepted"
        ).lower().strip()

        mapping = {
            "proposed":
                DecisionStatus.PROPOSED,
            "accepted":
                DecisionStatus.ACCEPTED,
            "rejected":
                DecisionStatus.REJECTED,
            "changed":
                DecisionStatus.CHANGED,
            "superseded":
                DecisionStatus.SUPERSEDED,
        }

        return mapping.get(
            normalized,
            DecisionStatus.ACCEPTED,
        )

    @staticmethod
    def _map_commitment_strength(
        value: Any,
    ) -> CommitmentStrength:

        normalized = str(
            value or "unassigned"
        ).lower().strip()

        mapping = {
            "firm":
                CommitmentStrength.FIRM,
            "weak":
                CommitmentStrength.WEAK,
            "request":
                CommitmentStrength.REQUEST,
            "unassigned":
                CommitmentStrength.UNASSIGNED,
        }

        return mapping.get(
            normalized,
            CommitmentStrength.UNASSIGNED,
        )

    # =========================================================
    # CONFIDENCE
    # =========================================================

    @staticmethod
    def _safe_confidence(
        value: Any,
        default: float = 0.0,
    ) -> float:

        try:
            confidence = float(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return default

        return max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )

    def _calculate_overall_confidence(
        self,
        decisions: list[Decision],
        commitments: list[Commitment],
        evidence: list[Evidence],
    ) -> float:

        values: list[float] = []

        for decision in decisions:
            values.append(
                self._safe_confidence(
                    decision.confidence
                )
            )

        for commitment in commitments:
            values.append(
                self._safe_confidence(
                    commitment.confidence
                )
            )

        for evidence_item in evidence:
            values.append(
                self._safe_confidence(
                    evidence_item.confidence
                )
            )

        if not values:
            return 0.0

        return round(
            sum(values) / len(values),
            4,
        )

    # =========================================================
    # DEDUPLICATION
    # =========================================================

    def _deduplicate_items(
        self,
        items: list[
            dict[str, Any]
        ],
        key_fields: list[str],
    ) -> list[
        dict[str, Any]
    ]:

        result: list[
            dict[str, Any]
        ] = []

        seen: set[str] = set()

        for item in items:

            values = []

            for field in key_fields:
                values.append(
                    self._clean_string(
                        item.get(
                            field
                        )
                    ).lower()
                )

            key = "|".join(values)

            if not key:
                continue

            if key in seen:
                continue

            seen.add(key)
            result.append(item)

        return result

    @staticmethod
    def _deduplicate_strings(
        values: list[str],
    ) -> list[str]:

        result = []
        seen = set()

        for value in values:

            clean = value.strip()

            if not clean:
                continue

            normalized = (
                clean.lower()
            )

            if normalized in seen:
                continue

            seen.add(normalized)
            result.append(clean)

        return result

    # =========================================================
    # SERIALIZATION
    # =========================================================

    @staticmethod
    def _decision_to_dict(
        decision: Decision,
    ) -> dict[str, Any]:

        return {
            "id": str(
                decision.id
            ),
            "meeting_id": str(
                decision.meeting_id
            ),
            "title":
                decision.title,
            "description":
                decision.description,
            "status":
                decision.status.value,
            "confidence":
                decision.confidence,
            "changed_from_decision_id": (
                str(
                    decision.changed_from_decision_id
                )
                if decision.changed_from_decision_id
                else None
            ),
            "created_at": (
                decision.created_at.isoformat()
                if decision.created_at
                else None
            ),
        }

    @staticmethod
    def _commitment_to_dict(
        commitment: Commitment,
    ) -> dict[str, Any]:

        return {
            "id": str(
                commitment.id
            ),
            "meeting_id": str(
                commitment.meeting_id
            ),
            "owner_id": (
                str(
                    commitment.owner_id
                )
                if commitment.owner_id
                else None
            ),
            "task":
                commitment.task,
            "deadline": (
                commitment.deadline.isoformat()
                if commitment.deadline
                else None
            ),
            "deadline_text":
                commitment.deadline_text,
            "strength":
                commitment.strength.value,
            "status":
                commitment.status.value,
            "confidence":
                commitment.confidence,
            "notes":
                commitment.notes,
            "created_at": (
                commitment.created_at.isoformat()
                if commitment.created_at
                else None
            ),
            "updated_at": (
                commitment.updated_at.isoformat()
                if commitment.updated_at
                else None
            ),
        }

    @staticmethod
    def _evidence_to_dict(
        evidence: Evidence,
    ) -> dict[str, Any]:

        return {
            "id": str(
                evidence.id
            ),
            "meeting_id": str(
                evidence.meeting_id
            ),
            "transcript_segment_id": (
                str(
                    evidence.transcript_segment_id
                )
                if evidence.transcript_segment_id
                else None
            ),
            "commitment_id": (
                str(
                    evidence.commitment_id
                )
                if evidence.commitment_id
                else None
            ),
            "decision_id": (
                str(
                    evidence.decision_id
                )
                if evidence.decision_id
                else None
            ),
            "evidence_type":
                evidence.evidence_type,
            "snippet":
                evidence.snippet,
            "confidence":
                evidence.confidence,
            "created_at": (
                evidence.created_at.isoformat()
                if evidence.created_at
                else None
            ),
        }

    # =========================================================
    # TEXT HELPERS
    # =========================================================

    @staticmethod
    def _clean_string(
        value: Any,
    ) -> str:

        if value is None:
            return ""

        if not isinstance(
            value,
            str,
        ):
            value = str(value)

        return value.strip()

    @classmethod
    def _clean_string_list(
        cls,
        values: Any,
    ) -> list[str]:

        if not isinstance(
            values,
            list,
        ):
            return []

        result = []

        for value in values:

            clean = cls._clean_string(
                value
            )

            if clean:
                result.append(
                    clean
                )

        return cls._deduplicate_strings(
            result
        )

    @staticmethod
    def _tokenize(
        text: str,
    ) -> list[str]:

        if not text:
            return []

        import re

        return re.findall(
            r"[a-zA-Z0-9]+",
            text.lower(),
        )

    @staticmethod
    def _make_snippet(
        text: str,
        max_length: int = 500,
    ) -> str:

        text = text.strip()

        if len(text) <= max_length:
            return text

        return (
            text[
                : max_length - 3
            ].rstrip()
            + "..."
        )

    @staticmethod
    def _format_chunk(
        chunk: list[
            TranscriptSegment
        ],
    ) -> str:

        lines = []

        for segment in chunk:

            speaker = (
                segment.speaker_name
                or segment.speaker_label
                or "Speaker"
            )

            lines.append(
                f"[{segment.start_time:.2f}s - "
                f"{segment.end_time:.2f}s] "
                f"{speaker}: "
                f"{segment.text.strip()}"
            )

        return "\n".join(
            lines
        )

    @staticmethod
    def _json_for_prompt(
        value: Any,
    ) -> str:

        import json

        return json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        )


analysis_service = AnalysisService()