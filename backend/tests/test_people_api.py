import unittest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.database import Base, get_db
from app.main import app
from app.models.person import Person
from app.models.participant import Participant


class PeopleAPITests(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        Base.metadata.create_all(self.engine)

        def override_db():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def create_person(self, name="Alex Morgan"):
        response = self.client.post(
            "/api/people",
            json={"display_name": name},
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def create_participant(self):
        from app.models.meeting import Meeting

        with Session(self.engine) as session:
            meeting = Meeting(
                id=uuid4(),
                title="Identity Test Meeting",
            )
            session.add(meeting)
            session.flush()

            participant = Participant(
                id=uuid4(),
                meeting_id=meeting.id,
                name="Alex",
            )
            session.add(participant)
            session.commit()

            return str(participant.id)

    def test_create_person(self):
        person = self.create_person()
        self.assertEqual(person["display_name"], "Alex Morgan")
        self.assertTrue(person["id"])

    def test_list_people(self):
        self.create_person("Alex Morgan")
        self.create_person("Jordan Lee")

        response = self.client.get("/api/people")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["total"], 2)

    def test_blank_name_rejected(self):
        response = self.client.post(
            "/api/people",
            json={"display_name": "   "},
        )
        self.assertEqual(response.status_code, 422)

    def test_missing_person(self):
        response = self.client.get(
            f"/api/people/{uuid4()}"
        )
        self.assertEqual(response.status_code, 404)

    def test_link_and_unlink(self):
        person = self.create_person()
        participant_id = self.create_participant()

        url = (
            f"/api/people/{person['id']}"
            f"/participants/{participant_id}"
        )

        linked = self.client.post(url)
        self.assertEqual(linked.status_code, 200)
        self.assertEqual(
            linked.json()["participant"]["person_id"],
            person["id"],
        )

        detail = self.client.get(
            f"/api/people/{person['id']}"
        )
        self.assertEqual(
            detail.json()["total_participants"], 1
        )

        unlinked = self.client.delete(url)
        self.assertEqual(unlinked.status_code, 200)

        detail = self.client.get(
            f"/api/people/{person['id']}"
        )
        self.assertEqual(
            detail.json()["total_participants"], 0
        )

    def test_duplicate_link_is_safe(self):
        person = self.create_person()
        participant_id = self.create_participant()

        url = (
            f"/api/people/{person['id']}"
            f"/participants/{participant_id}"
        )

        self.client.post(url)
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["already_linked"])

    def test_reassignment_requires_unlink(self):
        first = self.create_person("Alex Morgan")
        second = self.create_person("Another Alex")
        participant_id = self.create_participant()

        first_url = (
            f"/api/people/{first['id']}"
            f"/participants/{participant_id}"
        )

        second_url = (
            f"/api/people/{second['id']}"
            f"/participants/{participant_id}"
        )

        self.assertEqual(
            self.client.post(first_url).status_code, 200
        )

        self.assertEqual(
            self.client.post(second_url).status_code, 409
        )

    def test_missing_participant(self):
        person = self.create_person()

        response = self.client.post(
            f"/api/people/{person['id']}"
            f"/participants/{uuid4()}"
        )

        self.assertEqual(response.status_code, 404)

    def test_unlink_wrong_person_rejected(self):
        first = self.create_person("Alex Morgan")
        second = self.create_person("Jordan Lee")
        participant_id = self.create_participant()

        self.client.post(
            f"/api/people/{first['id']}"
            f"/participants/{participant_id}"
        )

        response = self.client.delete(
            f"/api/people/{second['id']}"
            f"/participants/{participant_id}"
        )

        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
