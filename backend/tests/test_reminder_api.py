import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db


def fake_db():
    yield object()


class ReminderAPITests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        app.dependency_overrides[get_db] = fake_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.pop(get_db, None)

    def test_successful_preview(self):
        expected = {
            "today": "2026-11-12",
            "days_ahead": 7,
            "counts": {
                "overdue": 1,
                "upcoming": 0,
                "needs_deadline_review": 0,
                "no_deadline": 0,
            },
            "overdue": [],
            "upcoming": [],
            "needs_deadline_review": [],
            "no_deadline": [],
            "delivery_enabled": False,
        }

        with patch(
            "app.api.reminders.get_reminder_preview",
            return_value=expected,
        ) as mock_service:
            response = self.client.get(
                "/api/reminders/preview?days_ahead=7"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        mock_service.assert_called_once()

    def test_custom_window(self):
        with patch(
            "app.api.reminders.get_reminder_preview",
            return_value={"days_ahead": 14},
        ) as mock_service:
            response = self.client.get(
                "/api/reminders/preview?days_ahead=14"
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["days_ahead"], 14)
        self.assertEqual(
            mock_service.call_args.kwargs["days_ahead"], 14
        )

    def test_rejects_zero_days(self):
        response = self.client.get(
            "/api/reminders/preview?days_ahead=0"
        )
        self.assertEqual(response.status_code, 422)

    def test_rejects_over_90_days(self):
        response = self.client.get(
            "/api/reminders/preview?days_ahead=91"
        )
        self.assertEqual(response.status_code, 422)

    def test_rejects_non_numeric_days(self):
        response = self.client.get(
            "/api/reminders/preview?days_ahead=abc"
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
