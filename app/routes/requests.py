# app/routes/requests.py

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Case, Request
from app.schemas import (
    RequestResponse,
    RequestTrackingCaseSummary,
    RequestTrackingListResponse,
    RequestTrackingResponse,
    RequestUpdate,
)
from app.services.email_service import send_email
from app.services.request_service import build_court_request, build_police_request

router = APIRouter(prefix="/requests", tags=["requests"])


def _serialize_request_tracking(item: Request) -> RequestTrackingResponse:
    case = item.case
    court = case.court if case else None
    document_count = len(item.documents or [])

    return RequestTrackingResponse(
        request_id=item.id,
        case_id=item.case_id,
        request_type=item.request_type,
        status=item.status,
        recipient_name=item.recipient_name,
        recipient_email=item.recipient_email,
        subject=item.subject,
        sent_at=item.sent_at,
        response_due_date=item.response_due_date,
        response_summary=item.response_summary,
        has_document=document_count > 0,
        document_count=document_count,
        case=RequestTrackingCaseSummary(
            case_id=case.id if case else item.case_id,
            external_case_id=case.external_case_id if case else None,
            title=case.title if case else None,
            case_status=case.status if case else None,
            court_name=court.name if court else None,
            court_city=court.city if court else None,
            selected_for_followup=bool(case.selected_for_followup) if case else False,
        ),
    )


@router.get("", response_model=list[RequestResponse])
def list_requests(db: Session = Depends(get_db)):
    return db.query(Request).order_by(Request.id.desc()).all()


@router.get("/tracking/open", response_model=RequestTrackingListResponse)
def list_open_requests(db: Session = Depends(get_db)):
    items = (
        db.query(Request)
        .options(
            joinedload(Request.case).joinedload(Case.court),
            joinedload(Request.documents),
        )
        .filter(Request.status != "replied")
        .order_by(Request.id.desc())
        .all()
    )

    result_items = [_serialize_request_tracking(item) for item in items]
    return RequestTrackingListResponse(count=len(result_items), items=result_items)


@router.get("/tracking/replied", response_model=RequestTrackingListResponse)
def list_replied_requests(db: Session = Depends(get_db)):
    items = (
        db.query(Request)
        .options(
            joinedload(Request.case).joinedload(Case.court),
            joinedload(Request.documents),
        )
        .filter(Request.status == "replied")
        .order_by(Request.id.desc())
        .all()
    )

    result_items = [_serialize_request_tracking(item) for item in items]
    return RequestTrackingListResponse(count=len(result_items), items=result_items)


@router.get("/tracking/missing-documents", response_model=RequestTrackingListResponse)
def list_requests_missing_documents(db: Session = Depends(get_db)):
    items = (
        db.query(Request)
        .options(
            joinedload(Request.case).joinedload(Case.court),
            joinedload(Request.documents),
        )
        .order_by(Request.id.desc())
        .all()
    )

    filtered_items = [item for item in items if len(item.documents or []) == 0]
    result_items = [_serialize_request_tracking(item) for item in filtered_items]
    return RequestTrackingListResponse(count=len(result_items), items=result_items)


@router.get("/{request_id}", response_model=RequestResponse)
def get_request(request_id: int, db: Session = Depends(get_db)):
    item = db.query(Request).filter(Request.id == request_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")
    return item


@router.patch("/{request_id}", response_model=RequestResponse)
def update_request(request_id: int, payload: RequestUpdate, db: Session = Depends(get_db)):
    item = db.query(Request).filter(Request.id == request_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")

    if payload.recipient_name is not None:
        item.recipient_name = payload.recipient_name
    if payload.recipient_email is not None:
        item.recipient_email = payload.recipient_email
    if payload.subject is not None:
        item.subject = payload.subject
    if payload.body is not None:
        item.body = payload.body
    if payload.status is not None:
        item.status = payload.status
    if payload.response_due_date is not None:
        item.response_due_date = payload.response_due_date
    if payload.response_summary is not None:
        item.response_summary = payload.response_summary

    db.commit()
    db.refresh(item)
    return item


@router.post("/{request_id}/approve", response_model=RequestResponse)
def approve_request(request_id: int, db: Session = Depends(get_db)):
    item = db.query(Request).filter(Request.id == request_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")

    item.status = "approved"
    db.commit()
    db.refresh(item)
    return item


@router.post("/{request_id}/mark-replied", response_model=RequestResponse)
def mark_request_replied(request_id: int, db: Session = Depends(get_db)):
    item = db.query(Request).filter(Request.id == request_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")

    item.status = "replied"
    db.commit()
    db.refresh(item)
    return item


@router.post("/{request_id}/send", response_model=RequestResponse)
def send_single_request(request_id: int, db: Session = Depends(get_db)):
    item = db.query(Request).filter(Request.id == request_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Request not found")

    if item.status != "approved":
        raise HTTPException(status_code=400, detail="Only approved requests can be sent")

    if not item.recipient_email:
        raise HTTPException(status_code=400, detail="Recipient email is missing")

    try:
        send_email(
            to_email=item.recipient_email,
            subject=item.subject,
            body=item.body,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sending failed: {str(e)}")

    item.status = "sent"
    item.sent_at = datetime.now(UTC).isoformat()
    db.commit()
    db.refresh(item)
    return item


@router.post("/send-approved")
def send_all_approved_requests(db: Session = Depends(get_db)):
    items = (
        db.query(Request)
        .filter(Request.status == "approved")
        .order_by(Request.id.asc())
        .all()
    )

    results = []

    for item in items:
        if not item.recipient_email:
            results.append(
                {
                    "request_id": item.id,
                    "status": "skipped",
                    "reason": "recipient_email missing",
                }
            )
            continue

        try:
            send_email(
                to_email=item.recipient_email,
                subject=item.subject,
                body=item.body,
            )
            item.status = "sent"
            item.sent_at = datetime.now(UTC).isoformat()
            results.append(
                {
                    "request_id": item.id,
                    "status": "sent",
                }
            )
        except Exception as e:
            results.append(
                {
                    "request_id": item.id,
                    "status": "failed",
                    "reason": str(e),
                }
            )

    db.commit()
    return results


@router.post("/generate/court/{case_id}", response_model=RequestResponse)
def generate_court_request(case_id: int, db: Session = Depends(get_db)):
    case = (
        db.query(Case)
        .options(
            joinedload(Case.court),
            joinedload(Case.hearing_dates),
            joinedload(Case.parties),
        )
        .filter(Case.id == case_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    payload = build_court_request(case)
    item = Request(case_id=case.id, **payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/generate/police/{case_id}", response_model=RequestResponse)
def generate_police_request(case_id: int, db: Session = Depends(get_db)):
    case = (
        db.query(Case)
        .options(
            joinedload(Case.court),
            joinedload(Case.hearing_dates),
            joinedload(Case.parties),
        )
        .filter(Case.id == case_id)
        .first()
    )
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    payload = build_police_request(case)
    item = Request(case_id=case.id, **payload)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item