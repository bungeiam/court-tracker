from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Inquiry, InquiryBatch, InquiryMessage
from app.schemas import (
    InquiryMessageCreate,
    InquiryMessageResponse,
    InquiryResponse,
    InquiryUpdate,
)
from app.services.email_service import send_email

router = APIRouter(prefix="/inquiries", tags=["inquiries"])


@router.get("", response_model=list[InquiryResponse])
def list_inquiries(db: Session = Depends(get_db)):
    return db.query(Inquiry).order_by(Inquiry.id.desc()).all()


@router.get("/{inquiry_id}", response_model=InquiryResponse)
def get_inquiry(inquiry_id: int, db: Session = Depends(get_db)):
    item = (
        db.query(Inquiry)
        .options(
            joinedload(Inquiry.court),
            joinedload(Inquiry.batch),
            joinedload(Inquiry.messages),
        )
        .filter(Inquiry.id == inquiry_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Inquiry not found")
    return item


@router.patch("/{inquiry_id}", response_model=InquiryResponse)
def update_inquiry(
    inquiry_id: int,
    payload: InquiryUpdate,
    db: Session = Depends(get_db),
):
    item = db.query(Inquiry).filter(Inquiry.id == inquiry_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inquiry not found")

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
    if payload.sent_at is not None:
        item.sent_at = payload.sent_at
    if payload.acknowledged_at is not None:
        item.acknowledged_at = payload.acknowledged_at
    if payload.responded_at is not None:
        item.responded_at = payload.responded_at
    if payload.notes is not None:
        item.notes = payload.notes

    db.commit()
    db.refresh(item)
    return item


@router.post("/{inquiry_id}/approve", response_model=InquiryResponse)
def approve_inquiry(inquiry_id: int, db: Session = Depends(get_db)):
    item = db.query(Inquiry).filter(Inquiry.id == inquiry_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inquiry not found")

    item.status = "approved"
    db.commit()
    db.refresh(item)
    return item


@router.post("/{inquiry_id}/send", response_model=InquiryResponse)
def send_single_inquiry(inquiry_id: int, db: Session = Depends(get_db)):
    item = (
        db.query(Inquiry)
        .options(joinedload(Inquiry.batch))
        .filter(Inquiry.id == inquiry_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Inquiry not found")

    if item.status != "approved":
        raise HTTPException(status_code=400, detail="Only approved inquiries can be sent")

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

    if item.batch:
        sibling_statuses = [inquiry.status for inquiry in item.batch.inquiries]
        if all(status in {"sent", "acknowledged", "responded"} for status in sibling_statuses):
            item.batch.status = "sent"
        else:
            item.batch.status = "in_progress"

    db.commit()
    db.refresh(item)
    return item


@router.post("/send-approved")
def send_all_approved_inquiries(db: Session = Depends(get_db)):
    items = (
        db.query(Inquiry)
        .filter(Inquiry.status == "approved")
        .order_by(Inquiry.id.asc())
        .all()
    )

    results = []

    for item in items:
        if not item.recipient_email:
            results.append(
                {
                    "inquiry_id": item.id,
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
            item.sent_at = datetime.utcnow().isoformat()
            results.append(
                {
                    "inquiry_id": item.id,
                    "status": "sent",
                }
            )
        except Exception as e:
            results.append(
                {
                    "inquiry_id": item.id,
                    "status": "failed",
                    "reason": str(e),
                }
            )

    batch_ids = {item.batch_id for item in items}
    for batch_id in batch_ids:
        batch = db.query(InquiryBatch).filter(InquiryBatch.id == batch_id).first()
        if not batch:
            continue

        statuses = [inquiry.status for inquiry in batch.inquiries]
        if statuses and all(status in {"sent", "acknowledged", "responded"} for status in statuses):
            batch.status = "sent"
        elif any(status in {"sent", "acknowledged", "responded"} for status in statuses):
            batch.status = "in_progress"

    db.commit()
    return results


@router.post("/{inquiry_id}/messages", response_model=InquiryMessageResponse)
def create_inquiry_message(
    inquiry_id: int,
    payload: InquiryMessageCreate,
    db: Session = Depends(get_db),
):
    inquiry = db.query(Inquiry).filter(Inquiry.id == inquiry_id).first()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")

    item = InquiryMessage(
        inquiry_id=inquiry_id,
        message_type=payload.message_type,
        sender=payload.sender,
        subject=payload.subject,
        body=payload.body,
        received_at=payload.received_at,
        file_path=payload.file_path,
        mime_type=payload.mime_type,
        notes=payload.notes,
    )

    db.add(item)
    db.flush()

    timestamp = payload.received_at or datetime.utcnow().isoformat()

    if payload.message_type == "ack":
        inquiry.acknowledged_at = timestamp
        inquiry.status = "acknowledged"
    elif payload.message_type == "response":
        inquiry.responded_at = timestamp
        inquiry.status = "responded"

    batch = db.query(InquiryBatch).filter(InquiryBatch.id == inquiry.batch_id).first()
    if batch:
        statuses = [sibling.status for sibling in batch.inquiries]
        if statuses and all(status == "responded" for status in statuses):
            batch.status = "completed"
        elif any(status in {"acknowledged", "responded"} for status in statuses):
            batch.status = "in_progress"

    db.commit()
    db.refresh(item)
    return item


@router.get("/{inquiry_id}/messages", response_model=list[InquiryMessageResponse])
def list_inquiry_messages(inquiry_id: int, db: Session = Depends(get_db)):
    inquiry = db.query(Inquiry).filter(Inquiry.id == inquiry_id).first()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")

    return (
        db.query(InquiryMessage)
        .filter(InquiryMessage.inquiry_id == inquiry_id)
        .order_by(InquiryMessage.id.desc())
        .all()
    )


@router.get("/messages/{message_id}", response_model=InquiryMessageResponse)
def get_inquiry_message(message_id: int, db: Session = Depends(get_db)):
    item = db.query(InquiryMessage).filter(InquiryMessage.id == message_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inquiry message not found")
    return item