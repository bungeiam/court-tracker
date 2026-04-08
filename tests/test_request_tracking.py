# tests/test_request_tracking.py

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client(tmp_path):
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

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
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


def create_case(
    client,
    court_id,
    *,
    title,
    selected_for_followup=0,
    external_case_id=None,
    status="new",
):
    response = client.post(
        "/cases",
        json={
            "court_id": court_id,
            "external_case_id": external_case_id,
            "case_type": "rikosasia",
            "title": title,
            "summary": f"{title} / testitapaus",
            "public_status": "scheduled",
            "source_method": "manual",
            "source_reference": "testi",
            "raw_text": title,
            "interest_score": 55,
            "interest_notes": "testimerkintä",
            "selected_for_followup": selected_for_followup,
            "status": status,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def create_request(client, case_id, request_type="court"):
    response = client.post(f"/requests/generate/{request_type}/{case_id}")
    assert response.status_code == 200, response.text
    return response.json()


def attach_document_to_request(client, case_id, request_id, title="Saapunut asiakirja"):
    response = client.post(
        f"/documents/case/{case_id}",
        json={
            "document_type": "decision",
            "title": title,
            "description": "Liitetty requestiin",
            "request_id": request_id,
            "source": "court",
            "sender": "paijat-hame.ko@oikeus.fi",
            "file_path": None,
            "mime_type": None,
            "public_status": "public",
            "received_date": "2026-04-08",
            "notes": "testidokumentti",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_request_tracking_lists_open_and_replied_requests(client):
    court = create_court(client)

    open_case = create_case(
        client,
        court["id"],
        title="Törkeä pahoinpitely",
        selected_for_followup=1,
        external_case_id="R 26/1400",
    )
    replied_case = create_case(
        client,
        court["id"],
        title="Huumausainerikos",
        selected_for_followup=1,
        external_case_id="R 26/1401",
    )

    open_request = create_request(client, open_case["id"], request_type="court")
    replied_request = create_request(client, replied_case["id"], request_type="police")

    mark_replied_response = client.post(f"/requests/{replied_request['id']}/mark-replied")
    assert mark_replied_response.status_code == 200, mark_replied_response.text

    open_response = client.get("/requests/tracking/open")
    assert open_response.status_code == 200, open_response.text
    open_data = open_response.json()

    assert open_data["count"] == 1
    assert open_data["items"][0]["request_id"] == open_request["id"]
    assert open_data["items"][0]["status"] != "replied"
    assert open_data["items"][0]["case"]["external_case_id"] == "R 26/1400"
    assert open_data["items"][0]["case"]["court_name"] == "Päijät-Hämeen käräjäoikeus"

    replied_response = client.get("/requests/tracking/replied")
    assert replied_response.status_code == 200, replied_response.text
    replied_data = replied_response.json()

    assert replied_data["count"] == 1
    assert replied_data["items"][0]["request_id"] == replied_request["id"]
    assert replied_data["items"][0]["status"] == "replied"
    assert replied_data["items"][0]["case"]["external_case_id"] == "R 26/1401"


def test_request_tracking_lists_requests_missing_documents(client):
    court = create_court(client)

    case_with_missing_docs = create_case(
        client,
        court["id"],
        title="Petos",
        selected_for_followup=1,
        external_case_id="R 26/1500",
    )
    case_with_document = create_case(
        client,
        court["id"],
        title="Törkeä varkaus",
        selected_for_followup=1,
        external_case_id="R 26/1501",
    )

    request_missing_docs = create_request(client, case_with_missing_docs["id"], request_type="court")
    request_with_document = create_request(client, case_with_document["id"], request_type="court")

    attach_document_to_request(
        client,
        case_with_document["id"],
        request_with_document["id"],
    )

    response = client.get("/requests/tracking/missing-documents")
    assert response.status_code == 200, response.text
    data = response.json()

    assert data["count"] == 1
    assert data["items"][0]["request_id"] == request_missing_docs["id"]
    assert data["items"][0]["has_document"] is False
    assert data["items"][0]["document_count"] == 0
    assert data["items"][0]["case"]["external_case_id"] == "R 26/1500"


def test_cases_tracking_lists_followup_cases_missing_requests(client):
    court = create_court(client)

    missing_request_case = create_case(
        client,
        court["id"],
        title="Törkeä pahoinpitely",
        selected_for_followup=1,
        external_case_id="R 26/1600",
        status="selected",
    )
    response = client.post(
        f"/cases/{missing_request_case['id']}/hearing-dates",
        json={
            "hearing_date": "2026-04-21",
            "hearing_type": "pääkäsittely",
            "notes": "testi",
        },
    )
    assert response.status_code == 200, response.text

    case_with_request = create_case(
        client,
        court["id"],
        title="Huumausainerikos",
        selected_for_followup=1,
        external_case_id="R 26/1601",
        status="selected",
    )
    create_request(client, case_with_request["id"], request_type="court")

    non_followup_case = create_case(
        client,
        court["id"],
        title="Liikennerikkomus",
        selected_for_followup=0,
        external_case_id="R 26/1602",
        status="new",
    )
    assert non_followup_case["selected_for_followup"] == 0

    tracking_response = client.get("/cases/tracking/missing-requests")
    assert tracking_response.status_code == 200, tracking_response.text
    tracking_data = tracking_response.json()

    assert tracking_data["count"] == 1
    assert tracking_data["items"][0]["case_id"] == missing_request_case["id"]
    assert tracking_data["items"][0]["external_case_id"] == "R 26/1600"
    assert tracking_data["items"][0]["selected_for_followup"] is True
    assert tracking_data["items"][0]["request_count"] == 0
    assert tracking_data["items"][0]["first_hearing_date"] == "2026-04-21"
    assert tracking_data["items"][0]["court_name"] == "Päijät-Hämeen käräjäoikeus"