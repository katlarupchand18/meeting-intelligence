import unittest
from unittest.mock import patch
from uuid import UUID

from app.services.meeting_relationship_service import (
    compare_meetings,
)


class MeetingRelationshipPromptTests(unittest.TestCase):

    def test_prompt_contract(self):
        first = {
            "id": "meeting-a",
            "title": "Planning",
            "created_at": "2026-10-01T10:00:00",
            "summary": "",
            "decisions": [],
            "commitments": [],
            "transcript": [
                {"id": "segment-a", "text": "We will review it."}
            ],
        }

        second = {
            "id": "meeting-b",
            "title": "Review",
            "created_at": "2026-10-08T10:00:00",
            "summary": "",
            "decisions": [],
            "commitments": [],
            "transcript": [
                {"id": "segment-b", "text": "We reviewed it."}
            ],
        }

        with (
            patch(
                "app.services.meeting_relationship_service.get_meeting_context",
                side_effect=[first, second],
            ),
            patch(
                "app.services.meeting_relationship_service.llm_service.generate_json",
                return_value={
                    "relationship": "uncertain",
                    "confidence": 0.0,
                    "explanation": "Insufficient evidence.",
                    "evidence": [],
                },
            ) as mocked_llm,
        ):
            result = compare_meetings(
                db=None,
                meeting_a_id=UUID("00000000-0000-0000-0000-000000000001"),
                meeting_b_id=UUID("00000000-0000-0000-0000-000000000002"),
            )

        prompt = mocked_llm.call_args.kwargs["prompt"]

        self.assertIn("Confidence must be a JSON NUMBER", prompt)
        self.assertIn("segment_id, quote, explanation", prompt)
        self.assertIn("BOTH meetings", prompt)
        self.assertIn(
            "Do not assume topic similarity proves continuation",
            prompt,
        )
        self.assertIn(
            "If evidence is insufficient, return uncertain",
            prompt,
        )
        self.assertEqual(result["relationship"], "uncertain")

    def test_same_meeting_rejected(self):
        meeting_id = UUID("00000000-0000-0000-0000-000000000001")
        with self.assertRaises(ValueError):
            compare_meetings(None, meeting_id, meeting_id)
