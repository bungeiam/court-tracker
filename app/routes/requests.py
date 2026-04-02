from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Case, Request
from app.schemas import RequestResponse, RequestUpdate
from app.services.request_service import build_court_request, build_police_request
from app.services.email_service import send_email

router = APIRouter(prefix="/requests", tags=["requests"])


@router.get("", response_model=list[RequestResponse])
def list_requests(db: Session = Depends(get_db)):
    return db.query(Request).order_by(Request.id.desc()).all()


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
    item.sent_at = datetime.utcnow().isoformat()
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
            results.append({
                "request_id": item.id,
                "status": "skipped",
                "reason": "recipient_email missing"
            })
            continue

        try:
            send_email(
                to_email=item.recipient_email,
                subject=item.subject,
                body=item.body,
            )
            item.status = "sent"
            item.sent_at = datetime.utcnow().isoformat()
            results.append({
                "request_id": item.id,
                "status": "sent"
            })
        except Exception as e:
            results.append({
                "request_id": item.id,
                "status": "failed",
                "reason": str(e)
            })

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