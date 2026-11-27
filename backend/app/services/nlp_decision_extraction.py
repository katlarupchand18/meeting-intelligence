"""
NLP-based Decision Extraction Service.

Extracts decision candidates using linguistic analysis, dependency parsing,
semantic similarity, and pattern matching - not relying solely on LLM.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.services.nlp_preprocessing_service import (
    NLPSentence,
    ProcessedTranscript,
    nlp_preprocessing_service,
)


@dataclass
class DecisionCandidate:
    """Represents a candidate decision extracted via NLP."""
    title: str
    description: str
    status: str  # proposed, accepted, rejected, changed, superseded
    confidence: float
    source_sentence: str
    speaker: str | None
    segment_id: UUID | None
    start_time: float | None
    end_time: float | None
    evidence_tokens: list[str] = field(default_factory=list)
    linguistic_features: dict[str, Any] = field(default_factory=dict)
    candidate_score: float = 0.0
    related_decisions: list[str] = field(default_factory=list)


class NLPDecisionExtractor:
    """
    Extracts decision candidates using NLP linguistic analysis.

    Pipeline:
    1. Identify decision indicator phrases
    2. Linguistic patterns for decision types
    3. Dependency parsing for subject/action
    4. Semantic similarity to decision patterns
    5. Negation and uncertainty detection
    6. Status classification (proposed/accepted/rejected/changed/superseded)
    7. Candidate scoring
    """

    # Decision indicator patterns
    DECISION_INDICATORS = [
        # Explicit decisions
        r"\b(?:decide|decided|decision|resolution|resolved)\b",
        r"\b(?:approve|approved|approval|reject|rejected|rejection)\b",
        r"\b(?:accept|accepted|acceptance|adopt|adopted|adoption)\b",
        r"\b(?:authorize|authorized|authorization)\b",
        r"\b(?:confirm|confirmed|confirmation)\b",
        r"\b(?:agree|agreed|agreement)\b",
        r"\b(?:motion\s+carried|motion\s+passed|carried|passed)\b",
        r"\b(?:vote|voted|voting)\b",

        # Status changes
        r"\b(?:change|changed|modify|modified|amend|amended)\b",
        r"\b(?:supersede|superseded|replace|replaced|override|overridden)\b",

        # Proposals
        r"\b(?:propose|proposed|proposal|suggest|suggested|suggestion)\b",
        r"\b(?:recommend|recommended|recommendation)\b",

        # Strong decision markers
        r"\b(?:it is (?:decided|resolved|agreed|approved)|we (?:decide|agree|approve|resolve))\b",
        r"\b(?:the (?:decision|resolution|agreement) is)\b",
    ]

    # Uncertainty/hedging patterns (lower confidence)
    UNCERTAINTY_PATTERNS = [
        r"\b(?:maybe|perhaps|possibly|might|could|may)\b",
        r"\b(?:think|believe|feel|seem|appear)\b",
        r"\b(?:probably|likely|unlikely|potentially)\b",
        r"\b(?:sort of|kind of|somewhat)\b",
    ]

    # Negation patterns
    NEGATION_PATTERNS = [
        r"\b(?:not|never|no|won't|will not|cannot|can't)\b",
        r"\b(?:don't|doesn't|didn't|isn't|aren't|wasn't|weren't)\b",
    ]

    def __init__(self) -> None:
        self.nlp_service = nlp_preprocessing_service
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self.decision_pattern = re.compile(
            "|".join(self.DECISION_INDICATORS), re.IGNORECASE
        )
        self.uncertainty_pattern = re.compile(
            "|".join(self.UNCERTAINTY_PATTERNS), re.IGNORECASE
        )
        self.negation_pattern = re.compile(
            "|".join(self.NEGATION_PATTERNS), re.IGNORECASE
        )

    def extract_candidates(
        self,
        processed: ProcessedTranscript,
    ) -> list[DecisionCandidate]:
        """
        Extract decision candidates from processed transcript.

        Args:
            processed: ProcessedTranscript from NLP preprocessing

        Returns:
            List of DecisionCandidate objects
        """
        candidates = []

        for sent_idx, sentence in enumerate(processed.sentences):
            # Check if sentence contains decision indicators
            if not self._has_decision_indicator(sentence.text):
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
        return [c for c in scored_candidates if c.candidate_score >= 0.25]

    def _has_decision_indicator(self, text: str) -> bool:
        """Check if text contains decision indicator phrases."""
        return bool(self.decision_pattern.search(text))

    def _has_uncertainty(self, text: str) -> bool:
        """Check if text contains uncertainty hedging."""
        return bool(self.uncertainty_pattern.search(text))

    def _is_negated(self, text: str) -> bool:
        """Check if decision is negated."""
        return bool(self.negation_pattern.search(text))

    def _extract_from_sentence(
        self,
        sentence: NLPSentence,
        sent_idx: int,
        processed: ProcessedTranscript,
    ) -> DecisionCandidate | None:
        """Extract decision candidate from a single sentence."""
        # Extract title and description
        title = self._extract_title(sentence)
        description = self._extract_description(sentence, title)

        if not title and not description:
            return None

        # Determine status
        status = self._determine_status(sentence)

        # Calculate confidence
        confidence = self._calculate_confidence(sentence, status)

        # Get evidence tokens
        evidence_tokens = self._get_evidence_tokens(sentence)

        # Linguistic features
        linguistic_features = self._extract_linguistic_features(sentence)

        return DecisionCandidate(
            title=title or "Decision",
            description=description or sentence.text,
            status=status,
            confidence=confidence,
            source_sentence=sentence.text,
            speaker=sentence.speaker,
            segment_id=sentence.segment_id,
            start_time=sentence.start_time,
            end_time=sentence.end_time,
            evidence_tokens=evidence_tokens,
            linguistic_features=linguistic_features,
        )

    def _extract_title(self, sentence: NLPSentence) -> str | None:
        """Extract a short title for the decision."""
        # Find key nouns and verbs
        key_terms = []
        for token in sentence.tokens:
            if token.pos in ("NOUN", "PROPN") and not token.is_stop and len(token.text) > 2:
                key_terms.append(token.text)
            elif token.pos == "VERB" and token.dep == "ROOT":
                key_terms.append(token.lemma)

        if key_terms:
            return " ".join(key_terms[:5])
        return None

    def _extract_description(self, sentence: NLPSentence, title: str | None) -> str:
        """Extract description from the sentence."""
        text = sentence.text

        # Remove speaker prefix
        if sentence.speaker and text.startswith(f"{sentence.speaker}:"):
            text = text[len(sentence.speaker) + 1:].strip()

        # If we have a title, make description more specific
        if title and title.lower() in text.lower():
            # Keep full sentence as description
            return text

        return text

    def _determine_status(self, sentence: NLPSentence) -> str:
        """Determine decision status from linguistic cues."""
        text_lower = sentence.text.lower()

        # Check for rejection
        if any(word in text_lower for word in ["reject", "rejected", "rejection", "denied", "declined", "vote against"]):
            return "rejected"

        # Check for superseded/changed
        if any(word in text_lower for word in ["supersede", "superseded", "replace", "replaced", "override", "overridden", "amend", "amended", "modify", "modified", "change", "changed"]):
            return "changed"

        # Check for proposal/suggestion
        if any(word in text_lower for word in ["propose", "proposed", "proposal", "suggest", "suggested", "suggestion", "recommend", "recommended", "recommendation"]):
            # But not if it's clearly accepted
            if any(word in text_lower for word in ["approved", "accepted", "adopted", "agreed", "carried", "passed", "resolved"]):
                return "accepted"
            return "proposed"

        # Check for acceptance/approval
        if any(word in text_lower for word in ["approve", "approved", "approval", "accept", "accepted", "acceptance", "adopt", "adopted", "adoption", "agree", "agreed", "agreement", "authorize", "authorized", "confirm", "confirmed", "motion carried", "motion passed", "carried", "passed", "resolved"]):
            return "accepted"

        # Default to proposed if uncertain
        if self._has_uncertainty(sentence.text):
            return "proposed"

        return "accepted"

    def _calculate_confidence(self, sentence: NLPSentence, status: str) -> float:
        """Calculate confidence score for the decision candidate."""
        score = 0.4  # Base score for having decision indicator

        text_lower = sentence.text.lower()

        # Strong explicit decision verbs
        if any(word in text_lower for word in ["decided", "resolved", "approved", "accepted", "adopted", "agreed", "carried", "passed", "motion carried", "motion passed"]):
            score += 0.3
        elif any(word in text_lower for word in ["reject", "rejected", "denied", "declined"]):
            score += 0.25
        elif any(word in text_lower for word in ["propose", "suggest", "recommend"]):
            score += 0.1

        # Penalty for uncertainty
        if self._has_uncertainty(sentence.text):
            score -= 0.15

        # Penalty for negation
        if self._is_negated(sentence.text):
            score -= 0.1

        # Boost for voting language
        if any(word in text_lower for word in ["vote", "voted", "voting", "unanimous", "majority"]):
            score += 0.15

        # Boost for formal language
        if any(word in text_lower for word in ["resolution", "motion", "hereby", "therefore", "accordingly"]):
            score += 0.1

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
            "uncertainty": self._has_uncertainty(sentence.text),
            "person_entities": [
                e.text for e in sentence.tokens if e.ent_type == "PERSON"
            ],
            "org_entities": [
                e.text for e in sentence.tokens if e.ent_type == "ORG"
            ],
        }

    def _score_candidates(
        self,
        candidates: list[DecisionCandidate],
        processed: ProcessedTranscript,
    ) -> list[DecisionCandidate]:
        """Score and rank candidates."""
        for candidate in candidates:
            score = candidate.confidence

            # Boost for explicit status
            if candidate.status in ("accepted", "rejected"):
                score += 0.1

            # Boost for speaker authority (if same speaker makes decisions)
            speaker_decisions = sum(
                1 for c in candidates if c.speaker == candidate.speaker
            )
            if speaker_decisions > 1:
                score += 0.05 * (speaker_decisions - 1)

            candidate.candidate_score = min(1.0, score)

        return sorted(candidates, key=lambda c: c.candidate_score, reverse=True)


# Singleton instance
nlp_decision_extractor = NLPDecisionExtractor()