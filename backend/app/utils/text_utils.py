import re


def normalize_text(text: str) -> str:
    """
    Normalize whitespace while preserving the actual meaning
    of the transcript.
    """

    if not text:
        return ""

    text = text.replace("\x00", " ")

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def clean_transcript_text(text: str) -> str:
    """
    Clean transcript text without aggressively modifying it.

    We intentionally avoid removing words because transcript
    wording may be required as evidence later.
    """

    if not text:
        return ""

    text = text.replace("\x00", " ")

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def truncate_text(
    text: str,
    max_length: int = 500,
) -> str:
    """
    Safely truncate text for previews and UI responses.
    """

    if len(text) <= max_length:
        return text

    return text[: max_length - 3].rstrip() + "..."


def split_into_sentences(
    text: str,
) -> list[str]:
    """
    Split text into simple sentence-like units.

    This is a lightweight utility. It is not intended to replace
    the LLM analysis layer.
    """

    if not text:
        return []

    cleaned = normalize_text(text)

    sentences = re.split(
        r"(?<=[.!?])\s+",
        cleaned,
    )

    return [
        sentence.strip()
        for sentence in sentences
        if sentence.strip()
    ]


def word_count(
    text: str,
) -> int:
    """
    Return the approximate number of words.
    """

    if not text:
        return 0

    return len(
        normalize_text(text).split()
    )


def contains_any_phrase(
    text: str,
    phrases: list[str],
) -> bool:
    """
    Check whether text contains any supplied phrase.
    """

    if not text:
        return False

    lowered = text.lower()

    return any(
        phrase.lower() in lowered
        for phrase in phrases
    )


def extract_keywords(
    text: str,
    stop_words: set[str] | None = None,
) -> list[str]:
    """
    Extract simple repeated keywords.

    This is only a lightweight utility. Final topic extraction
    will be performed by the AI analysis service.
    """

    if not text:
        return []

    if stop_words is None:
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "but",
            "is",
            "are",
            "was",
            "were",
            "to",
            "of",
            "in",
            "on",
            "for",
            "with",
            "this",
            "that",
            "it",
            "we",
            "you",
            "i",
            "he",
            "she",
            "they",
            "be",
            "have",
            "has",
            "had",
        }

    words = re.findall(
        r"\b[a-zA-Z][a-zA-Z0-9_-]{2,}\b",
        text.lower(),
    )

    counts: dict[str, int] = {}

    for word in words:
        if word in stop_words:
            continue

        counts[word] = counts.get(word, 0) + 1

    sorted_words = sorted(
        counts.items(),
        key=lambda item: (-item[1], item[0]),
    )

    return [
        word
        for word, _ in sorted_words
    ]