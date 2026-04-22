import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "test_court_tracker_ingest_preview.db"
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


def create_court(client, name, city, email):
    response = client.post(
        "/courts",
        json={
            "name": name,
            "court_level": "karajaoikeus",
            "city": city,
            "email": email,
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


def test_get_inquiry_ingest_preview_separates_secure_link_messages(client):
    court = create_court(
        client,
        name="Päijät-Hämeen käräjäoikeus",
        city="Lahti",
        email="paijat-hame.ko@oikeus.fi",
    )
    batch = create_inquiry_batch(client)

    generate_response = client.post(
        f"/inquiry-batches/{batch['id']}/generate",
        json={"court_ids": [court["id"]]},
    )
    assert generate_response.status_code == 200, generate_response.text

    inquiries_response = client.get("/inquiries")
    assert inquiries_response.status_code == 200, inquiries_response.text
    inquiry_id = inquiries_response.json()[0]["id"]

    ack_response = client.post(
        f"/inquiries/{inquiry_id}/messages",
        json={
            "message_type": "ack",
            "sender": "paijat-hame.ko@oikeus.fi",
            "subject": "Vastaanottokuittaus",
            "body": "Viesti on vastaanotettu.",
            "received_at": "2026-04-02T09:15:00+00:00",
            "notes": "Automaattinen kuittaus",
        },
    )
    assert ack_response.status_code == 200, ack_response.text

    secure_response = client.post(
        f"/inquiries/{inquiry_id}/messages",
        json={
            "message_type": "response",
            "raw_sender": "Turvaviesti <no-reply@securemail.example>",
            "raw_subject": "VS: Päijät-Hämeen käräjäoikeuden rikosasioiden käsittelytiedot 1.4.2026–30.4.2026",
            "source_email_message_id": "<message-id-123@example>",
            "secure_link_url": "https://securemail.example/message/abc123",
            "processing_status": "pending",
            "body": "Sisältää secure-linkin.",
            "received_at": "2026-04-03T11:30:00+00:00",
            "notes": "Secure-link viesti",
        },
    )
    assert secure_response.status_code == 200, secure_response.text

    processed_response = client.post(
        f"/inquiries/{inquiry_id}/messages",
        json={
            "message_type": "response",
            "sender": "paijat-hame.ko@oikeus.fi",
            "subject": "Käsittelytiedot liitteenä",
            "body": "Varsinainen vastaus.",
            "received_at": "2026-04-04T08:00:00+00:00",
            "processing_status": "fetched",
            "processed_at": "2026-04-04T08:05:00+00:00",
            "fetch_attempt_count": 1,
            "notes": "Jo käsitelty viesti",
        },
    )
    assert processed_response.status_code == 200, processed_response.text

    preview_response = client.get(f"/inquiries/{inquiry_id}/ingest-preview")
    assert preview_response.status_code == 200, preview_response.text

    data = preview_response.json()
    assert data["inquiry_id"] == inquiry_id
    assert data["inquiry_status"] == "responded"
    assert data["total_messages"] == 3
    assert data["secure_link_messages"] == 1
    assert data["response_messages"] == 2
    assert data["processed_messages"] == 1
    assert data["unprocessed_messages"] == 2
    assert data["latest_secure_link_url"] == "https://securemail.example/message/abc123"

    assert len(data["messages"]) == 3

    latest_message = data["messages"][0]
    assert latest_message["subject"] == "Käsittelytiedot liitteenä"
    assert latest_message["is_processed"] is True
    assert latest_message["has_secure_link"] is False

    secure_message = next(
        message for message in data["messages"] if message["has_secure_link"] is True
    )
    assert secure_message["secure_link_url"] == "https://securemail.example/message/abc123"
    assert secure_message["sender"] == "Turvaviesti <no-reply@securemail.example>"
    assert secure_message["subject"] == "VS: Päijät-Hämeen käräjäoikeuden rikosasioiden käsittelytiedot 1.4.2026–30.4.2026"
    assert secure_message["is_processed"] is False