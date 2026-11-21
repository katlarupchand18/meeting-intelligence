
import unittest
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.models.person import Person
from app.models.participant import Participant
from app.models.meeting import Meeting
from app.models.commitment import (
    Commitment,
    CommitmentStatus,
)
from app.services.person_insights_service import get_person_insights

import app.models


class PersonInsightsTests(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create_person(self, name="Alex"):
        person = Person(display_name=name)
        self.db.add(person)
        self.db.flush()
        return person

    def create_meeting(self, title):
        meeting = Meeting(title=title)
        self.db.add(meeting)
        self.db.flush()
        return meeting

    def create_participant(self, meeting, person, name="Alex"):
        participant = Participant(
            meeting_id=meeting.id,
            person_id=person.id,
            name=name,
        )
        self.db.add(participant)
        self.db.flush()
        return participant

    def create_commitment(
        self,
        meeting,
        participant,
        status=CommitmentStatus.OPEN,
        deadline=None,
    ):
        commitment = Commitment(
            meeting_id=meeting.id,
            owner_id=participant.id,
            task="Complete assigned task",
            status=status,
            deadline=deadline,
        )
        self.db.add(commitment)
        self.db.flush()
        return commitment

    def test_unknown_person(self):
        result = get_person_insights(self.db, uuid4())
        self.assertIsNone(result)

    def test_person_without_participants(self):
        person = self.create_person()
        result = get_person_insights(self.db, person.id)

        self.assertEqual(result["statistics"]["total_meetings"], 0)
        self.assertEqual(result["statistics"]["total_tasks"], 0)
        self.assertEqual(result["statistics"]["completion_rate"], 0)
        self.assertEqual(result["tasks"], [])

    def test_cross_meeting_aggregation(self):
        person = self.create_person()
        first = self.create_meeting("Meeting One")
        second = self.create_meeting("Meeting Two")

        p1 = self.create_participant(first, person)
        p2 = self.create_participant(second, person)

        self.create_commitment(first, p1)
        self.create_commitment(
            second, p2, CommitmentStatus.COMPLETED
        )

        result = get_person_insights(self.db, person.id)
        stats = result["statistics"]

        self.assertEqual(stats["total_meetings"], 2)
        self.assertEqual(stats["total_participant_records"], 2)
        self.assertEqual(stats["total_tasks"], 2)
        self.assertEqual(stats["completed_tasks"], 1)
        self.assertEqual(stats["pending_tasks"], 1)
        self.assertEqual(stats["completion_rate"], 50.0)

    def test_overdue_and_cancelled(self):
        person = self.create_person()
        meeting = self.create_meeting("Deadlines")
        participant = self.create_participant(meeting, person)

        yesterday = date.today() - timedelta(days=1)

        self.create_commitment(
            meeting,
            participant,
            CommitmentStatus.OPEN,
            yesterday,
        )
        self.create_commitment(
            meeting,
            participant,
            CommitmentStatus.CANCELLED,
            yesterday,
        )

        result = get_person_insights(self.db, person.id)
        stats = result["statistics"]

        self.assertEqual(stats["overdue_tasks"], 1)
        self.assertEqual(stats["cancelled_tasks"], 1)
        self.assertEqual(stats["pending_tasks"], 1)

    def test_other_person_excluded(self):
        first_person = self.create_person("Alex")
        second_person = self.create_person("Jordan")

        meeting = self.create_meeting("Shared Meeting")

        first = self.create_participant(
            meeting, first_person, "Alex"
        )
        second = self.create_participant(
            meeting, second_person, "Jordan"
        )

        self.create_commitment(meeting, first)
        self.create_commitment(meeting, second)

        result = get_person_insights(self.db, first_person.id)

        self.assertEqual(result["statistics"]["total_tasks"], 1)
        self.assertEqual(
            result["tasks"][0]["participant_id"],
            str(first.id),
        )


if __name__ == "__main__":
    unittest.main()
