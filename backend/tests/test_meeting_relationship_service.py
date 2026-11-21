import unittest

from app.services.meeting_relationship_service import (
    validate_relationship_result,
)


class MeetingRelationshipTests(unittest.TestCase):
    def setUp(self):
        self.contexts = [
            {
                "created_at": "2026-10-01T10:00:00",
                "transcript": [
                    {
                        "id": "first",
                        "text": "We will review the prototype next week.",
                    }
                ],
            },
            {
                "created_at": "2026-10-08T10:00:00",
                "transcript": [
                    {
                        "id": "second",
                        "text": "We are reviewing last week's prototype.",
                    }
                ],
            },
        ]

    def evidence(self):
        return [
            {
                "segment_id": "first",
                "quote": "review the prototype next week",
                "explanation": "Follow-up planned.",
            },
            {
                "segment_id": "second",
                "quote": "reviewing last week's prototype",
                "explanation": "Follow-up discussed.",
            },
        ]

    def classify(self, evidence, contexts=None):
        return validate_relationship_result(
            {
                "relationship": "continuation",
                "confidence": 0.9,
                "explanation": "Prototype follow-up.",
                "evidence": evidence,
            },
            self.contexts if contexts is None else contexts,
        )

    def test_valid_two_meeting_evidence(self):
        result = self.classify(self.evidence())
        self.assertEqual(result["relationship"], "continuation")
        self.assertEqual(len(result["evidence"]), 2)
        self.assertFalse(result["saved"])

    def test_one_sided_evidence_rejected(self):
        result = self.classify(self.evidence()[:1])
        self.assertEqual(result["relationship"], "uncertain")

    def test_fabricated_segment_rejected(self):
        evidence = self.evidence()
        evidence[1]["segment_id"] = "invented"
        result = self.classify(evidence)
        self.assertEqual(result["relationship"], "uncertain")

    def test_incorrect_quote_rejected(self):
        evidence = self.evidence()
        evidence[1]["quote"] = "This sentence does not exist."
        result = self.classify(evidence)
        self.assertEqual(result["relationship"], "uncertain")

    def test_reverse_chronology_rejected(self):
        contexts = [self.contexts[1], self.contexts[0]]
        result = self.classify(self.evidence(), contexts)
        self.assertEqual(result["relationship"], "uncertain")

    def test_confidence_is_bounded(self):
        result = validate_relationship_result(
            {
                "relationship": "unrelated",
                "confidence": 999,
                "evidence": [],
            },
            self.contexts,
        )
        self.assertEqual(result["confidence"], 1.0)

    def test_nan_confidence_rejected(self):
        result = validate_relationship_result(
            {
                "relationship": "uncertain",
                "confidence": "nan",
                "evidence": [],
            },
            self.contexts,
        )
        self.assertEqual(result["confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()
