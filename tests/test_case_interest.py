# tests/test_case_interest.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.services.case_service import assess_case_interest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test_court_tracker.db"
    database_url = f"sqlite:///{db_file}"

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    sent_emails = []

    def fake_send_email(to_email: str, subject: str, body: str):
        sent_emails.append(
            {
                "to_email": to_email,
                "subject": subject,
                "body": body,
            }
        )

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr("app.routes.inquiries.send_email", fake_send_email)

    with TestClient(app) as test_client:
        test_client.sent_emails = sent_emails
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def create_court(client):
    response = client.post(
        "/courts",
        json={
            "name": "Päijät-Hämeen käräjäoikeus",
            "court_level": "karajaoikeus",
            "city": "Lahti",
            "email": "paijat-hame.ko@oikeus.fi",
            "notes": "Virastoposti",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_inquiry_batch(client):
    response = client.post(
        "/inquiry-batches",
        json={
            "name": "Huhtikuu 2026 rikosasioiden tiedustelukierros",
            "start_date": "2026-04-01",
            "end_date": "2026-04-30",
            "notes": "Testibatch",
            "status": "draft",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_inquiry_for_court(client, court_id, batch_id):
    response = client.post(
        f"/inquiry-batches/{batch_id}/generate",
        json={"court_ids": [court_id]},
    )
    assert response.status_code == 200, response.text

    inquiries_response = client.get("/inquiries")
    assert inquiries_response.status_code == 200, inquiries_response.text

    inquiries = inquiries_response.json()
    assert len(inquiries) == 1
    return inquiries[0]["id"]


def create_response_message(client, inquiry_id, body):
    response = client.post(
        f"/inquiries/{inquiry_id}/messages",
        json={
            "message_type": "response",
            "sender": "paijat-hame.ko@oikeus.fi",
            "subject": "Käsittelytiedot",
            "body": body,
            "received_at": "2026-04-03T11:30:00",
            "notes": "Varsinainen vastaus",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_serious_offense_gets_higher_score_than_minor():
    serious = assess_case_interest(
        title="Törkeä pahoinpitely",
        summary="R 26/1234 Törkeä pahoinpitely, pääkäsittely 15.4.2026",
    )
    minor = assess_case_interest(
        title="Liikennerikkomus",
        summary="R 26/1250 Liikennerikkomus, pääkäsittely 16.4.2026",
    )

    assert serious.score > minor.score
    assert "vakava rikosnimike" in serious.notes
    assert "vähäinen asia" in minor.notes


def test_minor_case_gets_lower_score():
    minor = assess_case_interest(
        title="Näpistys",
        summary="R 26/1260 Näpistys, pääkäsittely 17.4.2026",
    )
    medium = assess_case_interest(
        title="Pahoinpitely",
        summary="R 26/1261 Pahoinpitely, pääkäsittely 18.4.2026",
    )

    assert minor.score < medium.score


def test_multiple_defendants_increase_score():
    single_defendant = assess_case_interest(
        title="Huumausainerikos",
        summary="R 26/1300 Huumausainerikos, pääkäsittely 20.4.2026",
        defendant_count=1,
    )
    multiple_defendants = assess_case_interest(
        title="Huumausainerikos",
        summary="R 26/1300 Huumausainerikos, pääkäsittely 20.4.2026",
        defendant_count=3,
    )

    assert multiple_defendants.score > single_defendant.score
    assert "useampi vastaaja" in multiple_defendants.notes


def test_create_cases_saves_interest_score_and_notes(client):
    court = create_court(client)
    batch = create_inquiry_batch(client)
    inquiry_id = create_inquiry_for_court(client, court["id"], batch["id"])

    message = create_response_message(
        client,
        inquiry_id,
        "R 26/1400 Törkeä pahoinpitely, pääkäsittely 21.4.2026",
    )

    create_cases_response = client.post(
        f"/inquiries/{inquiry_id}/create-cases",
        json={"message_id": message["id"]},
    )
    assert create_cases_response.status_code == 200, create_cases_response.text

    create_cases_data = create_cases_response.json()
    assert create_cases_data["created_count"] == 1

    created_case = create_cases_data["created_cases"][0]
    assert created_case["interest_score"] is not None
    assert created_case["interest_notes"]
    assert "vakava rikosnimike" in created_case["interest_notes"]

    case_detail_response = client.get(f"/cases/{created_case['case_id']}")
    assert case_detail_response.status_code == 200, case_detail_response.text

    case_detail = case_detail_response.json()
    assert case_detail["interest_score"] == created_case["interest_score"]
    assert case_detail["interest_notes"] == created_case["interest_notes"]