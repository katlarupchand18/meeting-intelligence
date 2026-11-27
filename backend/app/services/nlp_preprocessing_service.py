"""
NLP Preprocessing Pipeline for Meeting Intelligence.

Provides text normalization, sentence segmentation, tokenization, POS tagging,
named entity recognition, dependency parsing, speaker attribution, and
date/deadline extraction using spaCy.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

try:
    import spacy
    from spacy.tokens import Doc, Span, Token
    SPACY_AVAILABLE = True
except ImportError:
    spacy = None
    Doc = Span = Token = Any
    SPACY_AVAILABLE = False

from app.core.config import settings


@dataclass
class NLPToken:
    """Represents a token with linguistic annotations."""
    text: str
    lemma: str
    pos: str
    tag: str
    dep: str
    head_text: str
    head_idx: int
    idx: int
    is_alpha: bool
    is_stop: bool
    is_punct: bool
    ent_type: str
    ent_iob: str


@dataclass
class NLPSentence:
    """Represents a sentence with linguistic annotations."""
    text: str
    start_char: int
    end_char: int
    tokens: list[NLPToken]
    speaker: str | None = None
    segment_id: UUID | None = None
    start_time: float | None = None
    end_time: float | None = None


@dataclass
class NLPExtractedEntity:
    """Represents an extracted named entity."""
    text: str
    label: str
    start_char: int
    end_char: int
    sentence_idx: int
    confidence: float = 1.0


@dataclass
class NLPExtractedDate:
    """Represents an extracted date/deadline."""
    text: str
    parsed_date: datetime | None
    start_char: int
    end_char: int
    sentence_idx: int
    context: str


@dataclass
class ProcessedTranscript:
    """Complete processed transcript with all NLP annotations."""
    meeting_id: UUID
    sentences: list[NLPSentence] = field(default_factory=list)
    entities: list[NLPExtractedEntity] = field(default_factory=list)
    dates: list[NLPExtractedDate] = field(default_factory=list)
    speakers: set[str] = field(default_factory=set)
    processing_metadata: dict[str, Any] = field(default_factory=dict)


class NLPPreprocessingService:
    """
    NLP preprocessing pipeline for meeting transcripts.

    Uses spaCy for:
    - Text normalization
    - Sentence segmentation
    - Tokenization
    - POS tagging
    - Named entity recognition
    - Dependency parsing
    - Date/deadline extraction
    """

    _instance: NLPPreprocessingService | None = None
    _nlp: Any = None

    def __new__(cls) -> NLPPreprocessingService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._nlp is not None:
            return

        self.model_name = settings.SPACY_MODEL
        self._load_model()

    def _load_model(self) -> None:
        """Load spaCy model once at startup."""
        if not SPACY_AVAILABLE:
            raise RuntimeError(
                "spaCy not installed. Install with: pip install spacy && python -m spacy download en_core_web_sm"
            )

        try:
            self._nlp = spacy.load(self.model_name)
            # Add sentencizer if not present
            if "sentencizer" not in self._nlp.pipe_names:
                self._nlp.add_pipe("sentencizer", before="parser")
        except OSError:
            raise RuntimeError(
                f"spaCy model '{self.model_name}' not found. "
                f"Install with: python -m spacy download {self.model_name}"
            )

    @property
    def nlp(self) -> Any:
        """Get the loaded spaCy model."""
        if self._nlp is None:
            self._load_model()
        return self._nlp

    def process_transcript(
        self,
        meeting_id: UUID,
        segments: list[dict[str, Any]],
    ) -> ProcessedTranscript:
        """
        Process transcript segments through the NLP pipeline.

        Args:
            meeting_id: Meeting UUID
            segments: List of transcript segments with speaker, text, timestamps

        Returns:
            ProcessedTranscript with all NLP annotations
        """
        # Combine all text with segment markers
        full_text_parts = []
        segment_boundaries = []
        char_offset = 0

        for segment in segments:
            speaker = segment.get("speaker_name") or segment.get("speaker_label") or "Speaker"
            text = segment.get("text", "").strip()
            if not text:
                continue

            # Add speaker prefix
            speaker_text = f"{speaker}: {text}"
            full_text_parts.append(speaker_text)

            # Track boundaries for later mapping
            segment_boundaries.append({
                "start_char": char_offset,
                "end_char": char_offset + len(speaker_text),
                "speaker": speaker,
                "segment_id": segment.get("id"),
                "start_time": segment.get("start_time"),
                "end_time": segment.get("end_time"),
            })
            char_offset += len(speaker_text) + 1  # +1 for newline

        full_text = "\n".join(full_text_parts)

        # Process with spaCy
        doc = self.nlp(full_text)

        # Extract sentences with metadata
        sentences = []
        sentence_idx = 0

        for sent in doc.sents:
            # Find which segment this sentence belongs to
            segment_info = self._find_segment_for_sentence(
                sent, segment_boundaries
            )

            tokens = []
            for token in sent:
                tokens.append(NLPToken(
                    text=token.text,
                    lemma=token.lemma_,
                    pos=token.pos_,
                    tag=token.tag_,
                    dep=token.dep_,
                    head_text=token.head.text,
                    head_idx=token.head.i - sent.start,
                    idx=token.i - sent.start,
                    is_alpha=token.is_alpha,
                    is_stop=token.is_stop,
                    is_punct=token.is_punct,
                    ent_type=token.ent_type_,
                    ent_iob=token.ent_iob_,
                ))

            sentence = NLPSentence(
                text=sent.text,
                start_char=sent.start_char,
                end_char=sent.end_char,
                tokens=tokens,
                speaker=segment_info["speaker"] if segment_info else None,
                segment_id=segment_info["segment_id"] if segment_info else None,
                start_time=segment_info["start_time"] if segment_info else None,
                end_time=segment_info["end_time"] if segment_info else None,
            )
            sentences.append(sentence)
            sentence_idx += 1

        # Extract named entities
        entities = self._extract_entities(doc, sentences)

        # Extract dates/deadlines
        dates = self._extract_dates(doc, sentences)

        # Collect unique speakers
        speakers = set(s.speaker for s in sentences if s.speaker)

        return ProcessedTranscript(
            meeting_id=meeting_id,
            sentences=sentences,
            entities=entities,
            dates=dates,
            speakers=speakers,
            processing_metadata={
                "model": self.model_name,
                "num_sentences": len(sentences),
                "num_entities": len(entities),
                "num_dates": len(dates),
                "num_speakers": len(speakers),
            }
        )

    def _find_segment_for_sentence(
        self,
        sent: Span,
        segment_boundaries: list[dict],
    ) -> dict | None:
        """Find which transcript segment a sentence belongs to."""
        sent_mid = (sent.start_char + sent.end_char) // 2

        for boundary in segment_boundaries:
            if boundary["start_char"] <= sent_mid < boundary["end_char"]:
                return boundary

        # Fallback: find closest
        for boundary in segment_boundaries:
            if sent.start_char >= boundary["start_char"]:
                return boundary

        return segment_boundaries[0] if segment_boundaries else None

    def _extract_entities(
        self,
        doc: Doc,
        sentences: list[NLPSentence],
    ) -> list[NLPExtractedEntity]:
        """Extract named entities from the document."""
        entities = []

        for ent in doc.ents:
            # Find which sentence this entity belongs to
            sent_idx = None
            for i, sent in enumerate(sentences):
                if sent.start_char <= ent.start_char < sent.end_char:
                    sent_idx = i
                    break

            if sent_idx is not None:
                entities.append(NLPExtractedEntity(
                    text=ent.text,
                    label=ent.label_,
                    start_char=ent.start_char,
                    end_char=ent.end_char,
                    sentence_idx=sent_idx,
                ))

        return entities

    def _extract_dates(
        self,
        doc: Doc,
        sentences: list[NLPSentence],
    ) -> list[NLPExtractedDate]:
        """Extract dates and deadlines using NER and pattern matching."""
        dates = []

        # Date patterns - ordered by specificity (most specific first)
        date_patterns = [
            # Full date with time: "November 27 at 5 PM", "by November 28 at 12 PM"
            r"\bby\s+(?:the\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?\b",
            r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)\b",

            # Date with day of week: "Monday, November 27"
            r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),?\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?\b",

            # Relative dates with time: "next Monday at 5 PM"
            r"\b(?:next|this|last)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\s+(?:at\s+)?\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)\b",

            # Month day year: "November 27, 2026"
            r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b",

            # Simple month day: "November 27"
            r"\b(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(?:st|nd|rd|th)?\b",

            # Numeric dates
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",

            # Relative dates without time
            r"\b(?:next|this|last)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\b(?:today|tomorrow|yesterday)\b",
            r"\b(?:in|within)\s+\d+\s+(?:days?|weeks?|months?)\b",
            r"\bby\s+(?:the\s+)?(?:end\s+of\s+)?(?:this|next)\s+(?:week|month|quarter)\b",
            r"\bbefore\s+(?:the\s+)?(?:demo|meeting|deadline|release)\b",
            r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\b\d{1,2}(?:st|nd|rd|th)\s+(?:of\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december)\b",
        ]

        combined_pattern = re.compile("|".join(date_patterns), re.IGNORECASE)

        for sent in sentences:
            # Check NER dates first
            for token in sent.tokens:
                if token.ent_type == "DATE":
                    # Get surrounding context
                    context_start = max(0, token.idx - 5)
                    context_end = min(len(sent.tokens), token.idx + 6)
                    context = " ".join(t.text for t in sent.tokens[context_start:context_end])

                    dates.append(NLPExtractedDate(
                        text=token.text,
                        parsed_date=None,  # Would need dateparser for full parsing
                        start_char=sent.start_char + token.idx,
                        end_char=sent.start_char + token.idx + len(token.text),
                        sentence_idx=sentences.index(sent),
                        context=context,
                    ))

            # Check pattern-based dates
            for match in combined_pattern.finditer(sent.text):
                context_start = max(0, match.start() - 20)
                context_end = min(len(sent.text), match.end() + 20)
                context = sent.text[context_start:context_end]

                dates.append(NLPExtractedDate(
                    text=match.group(),
                    parsed_date=None,
                    start_char=sent.start_char + match.start(),
                    end_char=sent.start_char + match.end(),
                    sentence_idx=sentences.index(sent),
                    context=context,
                ))

        return dates


# Singleton instance
nlp_preprocessing_service = NLPPreprocessingService()