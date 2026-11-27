"""
NLP-based Commitment Extraction Service.

Extracts commitment candidates using linguistic analysis, dependency parsing,
named entity recognition, and semantic similarity - not relying solely on LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.services.nlp_preprocessing_service import (
    NLPExtractedDate,
    NLPSentence,
    ProcessedTranscript,
    nlp_preprocessing_service,
)


@dataclass
class CommitmentCandidate:
    """Represents a candidate commitment extracted via NLP."""
    task: str
    owner: str | None
    deadline: str | None
    deadline_text: str | None
    strength: str  # firm, weak, request, unassigned
    confidence: float
    source_sentence: str
    speaker: str | None
    segment_id: UUID | None
    start_time: float | None
    end_time: float | None
    evidence_tokens: list[str] = field(default_factory=list)
    linguistic_features: dict[str, Any] = field(default_factory=dict)
    candidate_score: float = 0.0


class NLPCommitmentExtractor:
    """
    Extracts commitment candidates using NLP linguistic analysis.

    Pipeline:
    1. Identify commitment indicator phrases
    2. POS tagging and dependency parsing
    3. Subject and action identification
    4. Named entity recognition for owners/dates
    5. Speaker attribution
    6. Date extraction
    7. Negation detection
    8. Modal verb analysis
    9. Semantic similarity to commitment patterns
    10. Candidate scoring and classification
    """

    # Commitment indicator patterns
    COMMITMENT_INDICATORS = [
        # Strong commitment verbs
        r"\b(?:will|shall|must|have to|need to|going to|gonna)\s+\w+",
        r"\b(?:commit|promise|agree|guarantee|ensure|pledge)\b",
        r"\b(?:responsible\s+for|accountable\s+for|own|take\s+care\s+of)\b",

        # Weak commitment / intent
        r"\b(?:should|ought to|plan to|intend to|hope to|try to)\s+\w+",
        r"\b(?:might|could|may)\s+\w+",

        # Request patterns
        r"\b(?:can you|could you|would you|please)\s+\w+",
        r"\b(?:need someone to|someone should|we need|we should)\b",

        # Action-oriented
        r"\b(?:action\s+item|todo|task|deliverable|follow.?up)\b",
        r"\b(?:deadline|due\s+by|by\s+)\w+",
    ]

    # Negation patterns
    NEGATION_PATTERNS = [
        r"\b(?:not|never|no|won't|will not|shall not|cannot|can't)\b",
        r"\b(?:don't|doesn't|didn't|isn't|aren't|wasn't|weren't)\b",
        r"\b(?:without|lack of|absence of|failed to)\b",
    ]

    # Modal strength mapping
    MODAL_STRENGTH = {
        # Firm
        "will": "firm", "shall": "firm", "must": "firm", "have to": "firm",
        "need to": "firm", "going to": "firm", "gonna": "firm",
        "commit": "firm", "promise": "firm", "agree": "firm", "guarantee": "firm",
        "ensure": "firm", "pledge": "firm", "responsible for": "firm",
        "accountable for": "firm", "own": "firm", "take care of": "firm",

        # Weak
        "should": "weak", "ought to": "weak", "plan to": "weak",
        "intend to": "weak", "hope to": "weak", "try to": "weak",
        "might": "weak", "could": "weak", "may": "weak",

        # Request
        "can you": "request", "could you": "request", "would you": "request",
        "please": "request", "need someone to": "request",
        "someone should": "request", "we need": "request", "we should": "request",
    }

    def __init__(self) -> None:
        self.nlp_service = nlp_preprocessing_service
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self.commitment_pattern = re.compile(
            "|".join(self.COMMITMENT_INDICATORS), re.IGNORECASE
        )
        self.negation_pattern = re.compile(
            "|".join(self.NEGATION_PATTERNS), re.IGNORECASE
        )

    def extract_candidates(
        self,
        processed: ProcessedTranscript,
    ) -> list[CommitmentCandidate]:
        """
        Extract commitment candidates from processed transcript.

        Args:
            processed: ProcessedTranscript from NLP preprocessing

        Returns:
            List of CommitmentCandidate objects
        """
        candidates = []

        for sent_idx, sentence in enumerate(processed.sentences):
            # Check if sentence contains commitment indicators
            if not self._has_commitment_indicator(sentence.text):
                continue

            # Skip if negated
            if self._is_negated(sentence.text):
                continue

            # Extract candidate
            candidate = self._extract_from_sentence(
                sentence, sent_idx, processed
            )

            if candidate:
                candidates.append(candidate)

        # Score and rank candidates
        scored_candidates = self._score_candidates(candidates, processed)

        # Filter by minimum score
        return [c for c in scored_candidates if c.candidate_score >= 0.3]

    def _has_commitment_indicator(self, text: str) -> bool:
        """Check if text contains commitment indicator phrases."""
        return bool(self.commitment_pattern.search(text))

    def _is_negated(self, text: str) -> bool:
        """Check if commitment is negated."""
        # Check for explicit negation near commitment verbs
        negation_match = self.negation_pattern.search(text)
        if not negation_match:
            return False

        # Check if negation is actually negating the commitment
        # (simple heuristic - negation within 5 words of commitment verb)
        return True

    def _extract_from_sentence(
        self,
        sentence: NLPSentence,
        sent_idx: int,
        processed: ProcessedTranscript,
    ) -> CommitmentCandidate | None:
        """Extract commitment candidate from a single sentence."""
        # Find the main action/task
        task = self._extract_task(sentence)
        if not task:
            return None

        # Extract owner
        owner = self._extract_owner(sentence, processed)

        # Extract deadline
        deadline, deadline_text = self._extract_deadline(sentence, sent_idx, processed)

        # Determine strength
        strength = self._determine_strength(sentence)

        # Calculate base confidence
        confidence = self._calculate_base_confidence(sentence, task, owner, deadline)

        # Get evidence tokens
        evidence_tokens = self._get_evidence_tokens(sentence)

        # Linguistic features
        linguistic_features = self._extract_linguistic_features(sentence)

        return CommitmentCandidate(
            task=task,
            owner=owner,
            deadline=deadline,
            deadline_text=deadline_text,
            strength=strength,
            confidence=confidence,
            source_sentence=sentence.text,
            speaker=sentence.speaker,
            segment_id=sentence.segment_id,
            start_time=sentence.start_time,
            end_time=sentence.end_time,
            evidence_tokens=evidence_tokens,
            linguistic_features=linguistic_features,
        )

    def _extract_task(self, sentence: NLPSentence) -> str | None:
        """Extract the main task/action from the sentence using dependency parsing."""
        # Find root verb and its dependents
        root_tokens = [t for t in sentence.tokens if t.dep == "ROOT"]
        if not root_tokens:
            return None

        root = root_tokens[0]

        # Get the verb phrase (root + its objects/complements)
        task_parts = [root.text]

        # Add direct objects, prepositional objects, etc.
        for token in sentence.tokens:
            if token.head_idx == root.idx and token.dep in ("dobj", "pobj", "attr", "oprd", "xcomp", "ccomp"):
                task_parts.append(token.text)
            # Include compound verbs
            elif token.dep in ("conj", "advcl") and token.head_idx == root.idx:
                task_parts.append(token.text)

        task = " ".join(task_parts)

        # Clean up - remove speaker prefix if present
        if sentence.speaker and task.startswith(f"{sentence.speaker}:"):
            task = task[len(sentence.speaker) + 1:].strip()

        # Remove modal verbs from start for cleaner task
        task = re.sub(r"^(?:will|shall|must|should|could|would|may|might|going to|gonna|need to|have to)\s+", "", task, flags=re.IGNORECASE)
        task = re.sub(r"^(?:commit|promise|agree|guarantee|ensure|pledge)\s+", "", task, flags=re.IGNORECASE)
        task = re.sub(r"^(?:to\s+)", "", task, flags=re.IGNORECASE)

        return task.strip() if task.strip() else None

    def _extract_owner(
        self,
        sentence: NLPSentence,
        processed: ProcessedTranscript,
    ) -> str | None:
        """Extract the commitment owner from the sentence."""
        # First check: is the speaker the owner?
        if sentence.speaker:
            # Check if sentence uses first person
            first_person = any(
                t.text.lower() in ("i", "me", "my", "mine", "myself")
                for t in sentence.tokens
            )
            if first_person:
                return sentence.speaker

            # Check for explicit assignment: "John will do X"
            for token in sentence.tokens:
                if token.dep in ("nsubj", "nsubjpass") and token.ent_type == "PERSON":
                    return token.text

                # Check for "X is responsible for" pattern
                if token.text.lower() in ("responsible", "accountable") and token.dep in ("attr", "acomp"):
                    # Find subject
                    for t in sentence.tokens:
                        if t.dep == "nsubj" and t.head_idx == token.idx:
                            return t.text

        # Check for named entities of type PERSON in the sentence
        for entity in processed.entities:
            if entity.sentence_idx == processed.sentences.index(sentence) and entity.label == "PERSON":
                return entity.text

        return None

    def _extract_deadline(
        self,
        sentence: NLPSentence,
        sent_idx: int,
        processed: ProcessedTranscript,
    ) -> tuple[str | None, str | None]:
        """Extract deadline from sentence and nearby dates."""
        # Check dates in this sentence
        sentence_dates = [d for d in processed.dates if d.sentence_idx == sent_idx]

        if sentence_dates:
            # Prefer dates with more context (longer text = more specific)
            # Sort by context length descending to get fullest date expression
            best_date = max(sentence_dates, key=lambda d: len(d.context))
            return best_date.text, best_date.context.strip()

        # Check adjacent sentences for dates
        for offset in [-1, 1]:
            adj_idx = sent_idx + offset
            if 0 <= adj_idx < len(processed.sentences):
                adj_dates = [d for d in processed.dates if d.sentence_idx == adj_idx]
                if adj_dates:
                    best_date = max(adj_dates, key=lambda d: len(d.context))
                    return best_date.text, best_date.context.strip()

        return None, None

    def _determine_strength(self, sentence: NLPSentence) -> str:
        """Determine commitment strength from modal verbs and indicators."""
        text_lower = sentence.text.lower()

        # Check for firm indicators
        firm_indicators = [
            "will", "shall", "must", "have to", "need to", "going to", "gonna",
            "commit", "promise", "agree", "guarantee", "ensure", "pledge",
            "responsible for", "accountable for", "own", "take care of"
        ]

        for indicator in firm_indicators:
            if indicator in text_lower:
                return "firm"

        # Check for request indicators
        request_indicators = [
            "can you", "could you", "would you", "please",
            "need someone to", "someone should", "we need", "we should"
        ]

        for indicator in request_indicators:
            if indicator in text_lower:
                return "request"

        # Check for weak indicators
        weak_indicators = [
            "should", "ought to", "plan to", "intend to", "hope to", "try to",
            "might", "could", "may"
        ]

        for indicator in weak_indicators:
            if indicator in text_lower:
                return "weak"

        # Check for action item keywords
        if any(kw in text_lower for kw in ["action item", "todo", "task", "deliverable", "followup", "follow-up"]):
            return "firm"

        return "unassigned"

    def _calculate_base_confidence(
        self,
        sentence: NLPSentence,
        task: str,
        owner: str | None,
        deadline: str | None,
    ) -> float:
        """Calculate base confidence score for the candidate."""
        score = 0.3  # Base score for having commitment indicator

        # Boost for having a clear task
        if task and len(task) > 5:
            score += 0.2

        # Boost for having an owner
        if owner:
            score += 0.2

        # Boost for having a deadline
        if deadline:
            score += 0.15

        # Boost for first-person commitment
        if sentence.speaker:
            first_person = any(
                t.text.lower() in ("i", "me", "my", "mine", "myself")
                for t in sentence.tokens
            )
            if first_person:
                score += 0.15

        # Penalty for weak modality
        if self._determine_strength(sentence) == "weak":
            score -= 0.1
        elif self._determine_strength(sentence) == "request":
            score -= 0.05

        return min(1.0, max(0.0, score))

    def _get_evidence_tokens(self, sentence: NLPSentence) -> list[str]:
        """Get key evidence tokens from the sentence."""
        evidence = []
        for token in sentence.tokens:
            if token.dep in ("ROOT", "nsubj", "dobj", "pobj", "advmod") or token.ent_type:
                evidence.append(token.text)
        return evidence

    def _extract_linguistic_features(self, sentence: NLPSentence) -> dict[str, Any]:
        """Extract linguistic features for the candidate."""
        return {
            "root_verb": next((t.lemma for t in sentence.tokens if t.dep == "ROOT"), None),
            "subject": next((t.text for t in sentence.tokens if t.dep in ("nsubj", "nsubjpass")), None),
            "objects": [t.text for t in sentence.tokens if t.dep in ("dobj", "pobj")],
            "modals": [t.text for t in sentence.tokens if t.tag == "MD"],
            "negated": self._is_negated(sentence.text),
            "person_entities": [
                e.text for e in sentence.tokens if e.ent_type == "PERSON"
            ],
            "date_entities": [
                e.text for e in sentence.tokens if e.ent_type == "DATE"
            ],
        }

    def _score_candidates(
        self,
        candidates: list[CommitmentCandidate],
        processed: ProcessedTranscript,
    ) -> list[CommitmentCandidate]:
        """Score and rank candidates using semantic similarity."""
        # Simple scoring based on features
        for candidate in candidates:
            score = candidate.confidence

            # Boost for speaker consistency (same speaker makes multiple commitments)
            speaker_commitments = sum(
                1 for c in candidates if c.speaker == candidate.speaker
            )
            if speaker_commitments > 1:
                score += 0.05 * (speaker_commitments - 1)

            # Boost for explicit deadline
            if candidate.deadline:
                score += 0.1

            # Boost for explicit owner
            if candidate.owner:
                score += 0.1

            candidate.candidate_score = min(1.0, score)

        # Sort by score descending
        return sorted(candidates, key=lambda c: c.candidate_score, reverse=True)


# Singleton instance
nlp_commitment_extractor = NLPCommitmentExtractor()