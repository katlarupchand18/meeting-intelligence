import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.services.reminder_service import get_reminder_preview


class FakeResult:
    def __init__(self, records):
        self.records = records

    def all(self):
        return self.records


class FakeSession:
    def __init__(self, commitments, meetings, participants):
        self.commitments = commitments
        self.meetings = meetings
        self.participants = participants

    def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]
        name = entity.__name__

        if name == "Commitment":
            return FakeResult(self.commitments)

        if name == "Meeting":
            return FakeResult(self.meetings)

        if name == "Participant":
            return FakeResult(self.participants)

        raise AssertionError(f"Unexpected query: {name}")


def make_commitment(
    meeting_id,
    owner_id,
    *,
    deadline=None,
    deadline_text=None,
    status="open",
):
    return SimpleNamespace(
        id=uuid4(),
        meeting_id=meeting_id,
        owner_id=owner_id,
        task="Test commitment",
        status=status,
        deadline=deadline,
        deadline_text=deadline_text,
        verification_status="pending",
        created_at=date.today(),
    )


class ReminderServiceTests(unittest.TestCase):

    def setUp(self):
        self.today = date.today()
        self.meeting_id = uuid4()
        self.owner_id = uuid4()

        self.meeting = SimpleNamespace(
            id=self.meeting_id,
            title="Test Meeting",
        )

        self.owner = SimpleNamespace(
            id=self.owner_id,
            name="Test Participant",
        )

    def preview(self, commitments, days_ahead=7):
        db = FakeSession(
            commitments,
            [self.meeting],
            [self.owner],
        )
        return get_reminder_preview(db, days_ahead)

    def commitment(self, **kwargs):
        return make_commitment(
            self.meeting_id,
            self.owner_id,
            **kwargs,
        )

    def test_overdue_deadline(self):
        commitment = self.commitment(
            deadline=self.today - timedelta(days=1)
        )
        result = self.preview([commitment])

        self.assertEqual(result["counts"]["overdue"], 1)
        self.assertEqual(
            result["overdue"][0]["owner_name"],
            "Test Participant",
        )

    def test_upcoming_deadline(self):
        commitment = self.commitment(
            deadline=self.today + timedelta(days=3)
        )
        result = self.preview([commitment])

        self.assertEqual(result["counts"]["upcoming"], 1)

    def test_future_deadline_outside_window(self):
        commitment = self.commitment(
            deadline=self.today + timedelta(days=20)
        )
        result = self.preview([commitment])

        self.assertEqual(
            sum(result["counts"].values()),
            0,
        )

    def test_text_deadline_requires_review(self):
        commitment = self.commitment(
            deadline_text="next Friday"
        )
        result = self.preview([commitment])

        self.assertEqual(
            result["counts"]["needs_deadline_review"],
            1,
        )

    def test_missing_deadline(self):
        commitment = self.commitment()
        result = self.preview([commitment])

        self.assertEqual(
            result["counts"]["no_deadline"],
            1,
        )

    def test_completed_and_cancelled_excluded(self):
        commitments = [
            self.commitment(
                status="completed",
                deadline=self.today - timedelta(days=2),
            ),
            self.commitment(
                status="cancelled",
                deadline=self.today - timedelta(days=3),
            ),
        ]

        result = self.preview(commitments)

        self.assertEqual(
            sum(result["counts"].values()),
            0,
        )


if __name__ == "__main__":
    unittest.main()
