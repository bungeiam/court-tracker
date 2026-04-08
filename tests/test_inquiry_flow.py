import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


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


def get_inquiry_id_by_court_id(inquiries, court_id):
    for item in inquiries:
        if item["court_id"] == court_id:
            return item["id"]
    raise AssertionError(f"Inquiry not found for court_id={court_id}")


def test_end_to_end_inquiry_to_cases_flow(client):
    court_1 = create_court(
        client,
        name="Päijät-Hämeen käräjäoikeus",
        city="Lahti",
        email="paijat-hame.ko@oikeus.fi",
    )
    court_2 = create_court(
        client,
        name="Kanta-Hämeen käräjäoikeus",
        city="Hämeenlinna",
        email="kanta-hame.ko@oikeus.fi",
    )

    batch = create_inquiry_batch(client)
    batch_id = batch["id"]

    generate_response = client.post(
        f"/inquiry-batches/{batch_id}/generate",
        json={"court_ids": [court_1["id"], court_2["id"]]},
    )
    assert generate_response.status_code == 200, generate_response.text
    generate_data = generate_response.json()

    assert generate_data["batch_id"] == batch_id
    assert generate_data["created_count"] == 2
    assert generate_data["skipped_count"] == 0

    batch_after_generate = client.get(f"/inquiry-batches/{batch_id}")
    assert batch_after_generate.status_code == 200, batch_after_generate.text
    assert batch_after_generate.json()["status"] == "generated"

    inquiries_response = client.get("/inquiries")
    assert inquiries_response.status_code == 200, inquiries_response.text
    inquiries = inquiries_response.json()
    assert len(inquiries) == 2

    inquiry_1_id = get_inquiry_id_by_court_id(inquiries, court_1["id"])
    inquiry_2_id = get_inquiry_id_by_court_id(inquiries, court_2["id"])

    inquiry_1_response = client.get(f"/inquiries/{inquiry_1_id}")
    assert inquiry_1_response.status_code == 200, inquiry_1_response.text
    inquiry_1 = inquiry_1_response.json()

    assert inquiry_1["status"] == "draft"
    assert inquiry_1["recipient_email"] == "paijat-hame.ko@oikeus.fi"
    assert "Päijät-Hämeen käräjäoikeus" in inquiry_1["subject"]
    assert "rikosasioiden käsittelytiedot" in inquiry_1["subject"]
    assert "2026-04-01" in inquiry_1["subject"]
    assert "2026-04-30" in inquiry_1["subject"]

    approve_response = client.post(f"/inquiries/{inquiry_1_id}/approve")
    assert approve_response.status_code == 200, approve_response.text
    assert approve_response.json()["status"] == "approved"

    send_response = client.post(f"/inquiries/{inquiry_1_id}/send")
    assert send_response.status_code == 200, send_response.text
    sent_inquiry = send_response.json()

    assert sent_inquiry["status"] == "sent"
    assert sent_inquiry["sent_at"] is not None
    assert len(client.sent_emails) == 1
    assert client.sent_emails[0]["to_email"] == "paijat-hame.ko@oikeus.fi"

    ack_response = client.post(
        f"/inquiries/{inquiry_1_id}/messages",
        json={
            "message_type": "ack",
            "sender": "paijat-hame.ko@oikeus.fi",
            "subject": "Vastaanottokuittaus",
            "body": "Viesti on vastaanotettu.",
            "received_at": "2026-04-02T09:15:00",
            "notes": "Automaattinen kuittaus",
        },
    )
    assert ack_response.status_code == 200, ack_response.text
    ack_message = ack_response.json()
    assert ack_message["message_type"] == "ack"

    inquiry_after_ack_response = client.get(f"/inquiries/{inquiry_1_id}")
    assert inquiry_after_ack_response.status_code == 200, inquiry_after_ack_response.text
    inquiry_after_ack = inquiry_after_ack_response.json()

    assert inquiry_after_ack["status"] == "acknowledged"
    assert inquiry_after_ack["acknowledged_at"] == "2026-04-02T09:15:00"

    response_message_response = client.post(
        f"/inquiries/{inquiry_1_id}/messages",
        json={
            "message_type": "response",
            "sender": "paijat-hame.ko@oikeus.fi",
            "subject": "Käsittelytiedot ajalle 1.4.2026–30.4.2026",
            "body": (
                "R 26/1234 Törkeä pahoinpitely, pääkäsittely 15.4.2026\n"
                "R 26/1250 Huumausainerikos, pääkäsittely 22.4.2026\n"
                "R 26/1301 Törkeä rattijuopumus, jatkokäsittely 28.4.2026"
            ),
            "received_at": "2026-04-03T11:30:00",
            "notes": "Varsinainen vastaus"
        },
    )
    assert response_message_response.status_code == 200, response_message_response.text
    response_message = response_message_response.json()
    assert response_message["message_type"] == "response"
    response_message_id = response_message["id"]

    inquiry_after_response = client.get(f"/inquiries/{inquiry_1_id}")
    assert inquiry_after_response.status_code == 200, inquiry_after_response.text
    inquiry_after_response_data = inquiry_after_response.json()

    assert inquiry_after_response_data["status"] == "responded"
    assert inquiry_after_response_data["responded_at"] == "2026-04-03T11:30:00"

    messages_response = client.get(f"/inquiries/{inquiry_1_id}/messages")
    assert messages_response.status_code == 200, messages_response.text
    messages = messages_response.json()
    assert len(messages) == 2
    assert {msg["message_type"] for msg in messages} == {"ack", "response"}

    create_cases_response = client.post(
        f"/inquiries/{inquiry_1_id}/create-cases",
        json={"message_id": response_message_id},
    )
    assert create_cases_response.status_code == 200, create_cases_response.text
    create_cases_data = create_cases_response.json()

    assert create_cases_data["inquiry_id"] == inquiry_1_id
    assert create_cases_data["message_id"] == response_message_id
    assert create_cases_data["parsed_count"] == 3
    assert create_cases_data["created_count"] == 3
    assert create_cases_data["duplicate_count"] == 0
    assert create_cases_data["skipped_count"] == 0

    cases_response = client.get("/cases")
    assert cases_response.status_code == 200, cases_response.text
    cases = cases_response.json()
    assert len(cases) == 3

    case_ids = [case["id"] for case in cases]

    case_details = []
    for case_id in case_ids:
        detail_response = client.get(f"/cases/{case_id}")
        assert detail_response.status_code == 200, detail_response.text
        case_details.append(detail_response.json())

    external_case_ids = {case["external_case_id"] for case in case_details}
    assert external_case_ids == {"R 26/1234", "R 26/1250", "R 26/1301"}

    hearing_dates_by_case = {
        case["external_case_id"]: case["hearing_dates"][0]["hearing_date"]
        for case in case_details
    }
    assert hearing_dates_by_case["R 26/1234"] == "2026-04-15"
    assert hearing_dates_by_case["R 26/1250"] == "2026-04-22"
    assert hearing_dates_by_case["R 26/1301"] == "2026-04-28"

    hearing_types_by_case = {
        case["external_case_id"]: case["hearing_dates"][0]["hearing_type"]
        for case in case_details
    }
    assert hearing_types_by_case["R 26/1234"] == "pääkäsittely"
    assert hearing_types_by_case["R 26/1250"] == "pääkäsittely"
    assert hearing_types_by_case["R 26/1301"] == "jatkokäsittely"

    batch_after_flow = client.get(f"/inquiry-batches/{batch_id}")
    assert batch_after_flow.status_code == 200, batch_after_flow.text
    assert batch_after_flow.json()["status"] in {"in_progress", "completed"}

    assert inquiry_2_id is not None


def test_generate_does_not_create_duplicate_inquiries_in_same_batch(client):
    court_1 = create_court(
        client,
        name="Päijät-Hämeen käräjäoikeus",
        city="Lahti",
        email="paijat-hame.ko@oikeus.fi",
    )
    court_2 = create_court(
        client,
        name="Kanta-Hämeen käräjäoikeus",
        city="Hämeenlinna",
        email="kanta-hame.ko@oikeus.fi",
    )

    batch = create_inquiry_batch(client)
    batch_id = batch["id"]

    first_generate = client.post(
        f"/inquiry-batches/{batch_id}/generate",
        json={"court_ids": [court_1["id"], court_2["id"]]},
    )
    assert first_generate.status_code == 200, first_generate.text
    assert first_generate.json()["created_count"] == 2

    second_generate = client.post(
        f"/inquiry-batches/{batch_id}/generate",
        json={"court_ids": [court_1["id"], court_2["id"]]},
    )
    assert second_generate.status_code == 200, second_generate.text
    second_data = second_generate.json()

    assert second_data["created_count"] == 0
    assert second_data["skipped_count"] == 2
    assert all(
        item["reason"] == "Inquiry already exists for this court in this batch"
        for item in second_data["skipped"]
    )

    list_inquiries_response = client.get("/inquiries")
    assert list_inquiries_response.status_code == 200, list_inquiries_response.text
    inquiries = list_inquiries_response.json()
    assert len(inquiries) == 2


def test_send_requires_approved_status(client):
    court = create_court(
        client,
        name="Päijät-Hämeen käräjäoikeus",
        city="Lahti",
        email="paijat-hame.ko@oikeus.fi",
    )

    batch = create_inquiry_batch(client)
    batch_id = batch["id"]

    generate_response = client.post(
        f"/inquiry-batches/{batch_id}/generate",
        json={"court_ids": [court["id"]]},
    )
    assert generate_response.status_code == 200, generate_response.text

    inquiries_response = client.get("/inquiries")
    assert inquiries_response.status_code == 200, inquiries_response.text
    inquiries = inquiries_response.json()
    assert len(inquiries) == 1

    inquiry_id = inquiries[0]["id"]

    send_response = client.post(f"/inquiries/{inquiry_id}/send")
    assert send_response.status_code == 400
    assert "Only approved inquiries can be sent" in send_response.text
    assert len(client.sent_emails) == 0