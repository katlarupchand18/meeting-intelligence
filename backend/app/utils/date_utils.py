import re
from datetime import date, datetime, timedelta


# ---------------------------------------------------------
# Date Formatting
# ---------------------------------------------------------

def format_date(
    value: date | datetime | None,
) -> str | None:
    """
    Convert a date/datetime to ISO format.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        return value.date().isoformat()

    return value.isoformat()


# ---------------------------------------------------------
# Deadline Text Detection
# ---------------------------------------------------------

def contains_relative_deadline(
    text: str,
) -> bool:
    """
    Check whether a statement contains a relative
    deadline phrase.

    Examples:
        tomorrow
        today
        next week
        next month
        next Friday
    """

    patterns = [
        r"\btoday\b",
        r"\btomorrow\b",
        r"\bday after tomorrow\b",
        r"\bnext week\b",
        r"\bnext month\b",
        r"\bnext year\b",
        r"\bnext monday\b",
        r"\bnext tuesday\b",
        r"\bnext wednesday\b",
        r"\bnext thursday\b",
        r"\bnext friday\b",
        r"\bnext saturday\b",
        r"\bnext sunday\b",
    ]

    lowered = text.lower()

    return any(
        re.search(pattern, lowered)
        for pattern in patterns
    )


# ---------------------------------------------------------
# Simple Relative Deadline Resolver
# ---------------------------------------------------------

def resolve_relative_deadline(
    text: str,
    reference_date: date | None = None,
) -> date | None:
    """
    Resolve simple relative deadlines.

    This intentionally handles only unambiguous expressions.
    Complex natural-language dates will later be handled by
    the AI analysis layer.
    """

    if reference_date is None:
        reference_date = date.today()

    lowered = text.lower()

    if "day after tomorrow" in lowered:
        return reference_date + timedelta(days=2)

    if "tomorrow" in lowered:
        return reference_date + timedelta(days=1)

    if "today" in lowered:
        return reference_date

    if "next week" in lowered:
        return reference_date + timedelta(days=7)

    if "next month" in lowered:
        month = reference_date.month + 1
        year = reference_date.year

        if month > 12:
            month = 1
            year += 1

        return date(
            year,
            month,
            min(
                reference_date.day,
                28,
            ),
        )

    return None


# ---------------------------------------------------------
# Overdue Check
# ---------------------------------------------------------

def is_overdue(
    deadline: date | None,
    current_date: date | None = None,
) -> bool:
    """
    Determine whether a deadline has passed.
    """

    if deadline is None:
        return False

    if current_date is None:
        current_date = date.today()

    return deadline < current_date