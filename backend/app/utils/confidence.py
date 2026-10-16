from typing import Iterable


def clamp_confidence(
    value: float | int | None,
) -> float:
    """
    Keep a confidence score between 0 and 1.
    """

    if value is None:
        return 0.0

    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(
        0.0,
        min(1.0, value),
    )


def average_confidence(
    values: Iterable[float | int | None],
) -> float:
    """
    Calculate the average confidence of multiple signals.
    """

    normalized = [
        clamp_confidence(value)
        for value in values
        if value is not None
    ]

    if not normalized:
        return 0.0

    return sum(normalized) / len(normalized)


def confidence_label(
    confidence: float | int | None,
) -> str:
    """
    Convert a confidence score into a human-readable label.
    """

    score = clamp_confidence(confidence)

    if score >= 0.85:
        return "high"

    if score >= 0.60:
        return "medium"

    return "low"


def confidence_percentage(
    confidence: float | int | None,
) -> int:
    """
    Convert a 0-1 confidence value into a percentage.
    """

    return round(
        clamp_confidence(confidence) * 100
    )


def combine_confidences(
    *values: float | int | None,
) -> float:
    """
    Combine multiple confidence signals using their average.
    """

    return average_confidence(values)