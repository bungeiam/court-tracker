import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Case, HearingDate, Inquiry, InquiryBatch, InquiryMessage
from app.schemas import (
    InquiryMessageCreate,
    InquiryMessageResponse,
    InquiryResponse,
    InquiryUpdate,
)
from app.services.email_service import send_email

router = APIRouter(prefix="/inquiries", tags=["inquiries"])


class CreateCasesPayload(BaseModel):
    message_id: int | None = None
    overwrite_source_reference: str | None = None


def _detect_hearing_type(text: str) -> str | None:
    lower_text = text.lower()

    if "pääkäsittely" in lower_text:
        return "pääkäsittely"
    if "jatkokäsittely" in lower_text:
        return "jatkokäsittely"
    if "valmisteluistunto" in lower_text:
        return "valmisteluistunto"
    if "istunto" in lower_text:
        return "istunto"

    return None


def _extract_date_iso(text: str) -> str | None:
    match = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", text)
    if not match:
        return None

    day, month, year = match.groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def _parse_case_line(line: str) -> dict | None:
    cleaned = " ".join(line.strip().split())
    if not cleaned:
        return None

    case_id_match = re.match(r"^([A-ZÅÄÖa-zåäö]\s*\d{1,4}/\d{1,6})\s+(.*)$", cleaned)
    if not case_id_match:
        return None

    external_case_id = re.sub(r"\s+", " ", case_id_match.group(1)).strip()
    rest = case_id_match.group(2).strip()

    title = rest
    if "," in rest:
        title = rest.split(",", 1)[0].strip()
    elif " - " in rest:
        title = rest.split(" - ", 1)[0].strip()

    hearing_date = _extract_date_iso(cleaned)
    hearing_type = _detect_hearing_type(cleaned)

    return {
        "external_case_id": external_case_id,
        "title": title or None,
        "summary": cleaned,
        "hearing_date": hearing_date,
        "hearing_type": hearing_type,
        "raw_text": cleaned,
    }


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


@router.post("/{inquiry_id}/create-cases")
def create_cases_from_inquiry(
    inquiry_id: int,
    payload: CreateCasesPayload,
    db: Session = Depends(get_db),
):
    inquiry = db.query(Inquiry).filter(Inquiry.id == inquiry_id).first()
    if not inquiry:
        raise HTTPException(status_code=404, detail="Inquiry not found")

    if payload.message_id is not None:
        message = (
            db.query(InquiryMessage)
            .filter(
                InquiryMessage.id == payload.message_id,
                InquiryMessage.inquiry_id == inquiry_id,
            )
            .first()
        )
        if not message:
            raise HTTPException(status_code=404, detail="Inquiry message not found for this inquiry")
    else:
        message = (
            db.query(InquiryMessage)
            .filter(
                InquiryMessage.inquiry_id == inquiry_id,
                InquiryMessage.message_type == "response",
            )
            .order_by(InquiryMessage.id.desc())
            .first()
        )
        if not message:
            raise HTTPException(status_code=400, detail="No response message found for this inquiry")

    if not message.body or not message.body.strip():
        raise HTTPException(status_code=400, detail="Response message body is empty")

    source_reference = payload.overwrite_source_reference or f"Inquiry {inquiry_id} / message {message.id}"

    raw_lines = [line.strip() for line in message.body.splitlines() if line.strip()]
    parsed_rows = []
    skipped_rows = []

    for index, line in enumerate(raw_lines, start=1):
        parsed = _parse_case_line(line)
        if parsed:
            parsed_rows.append(parsed)
        else:
            skipped_rows.append(
                {
                    "line_number": index,
                    "line": line,
                    "reason": "Could not parse case row",
                }
            )

    if not parsed_rows:
        raise HTTPException(status_code=400, detail="No case rows could be parsed from response message")

    created_cases = []
    duplicate_cases = []

    for row in parsed_rows:
        existing_case = (
            db.query(Case)
            .filter(
                Case.court_id == inquiry.court_id,
                Case.external_case_id == row["external_case_id"],
                Case.source_reference == source_reference,
            )
            .first()
        )
        if existing_case:
            duplicate_cases.append(
                {
                    "case_id": existing_case.id,
                    "external_case_id": existing_case.external_case_id,
                    "title": existing_case.title,
                    "reason": "Case already created from this inquiry response",
                }
            )
            continue

        new_case = Case(
            court_id=inquiry.court_id,
            external_case_id=row["external_case_id"],
            case_type="rikosasia",
            title=row["title"],
            summary=row["summary"],
            public_status="unknown",
            source_method="inquiry_response",
            source_reference=source_reference,
            raw_text=row["raw_text"],
            selected_for_followup=0,
            status="new",
        )
        db.add(new_case)
        db.flush()

        if row["hearing_date"]:
            hearing = HearingDate(
                case_id=new_case.id,
                hearing_date=row["hearing_date"],
                hearing_type=row["hearing_type"],
                notes="Created from inquiry response",
            )
            db.add(hearing)

        created_cases.append(
            {
                "case_id": new_case.id,
                "external_case_id": new_case.external_case_id,
                "title": new_case.title,
                "hearing_date": row["hearing_date"],
                "hearing_type": row["hearing_type"],
            }
        )

    db.commit()

    return {
        "inquiry_id": inquiry_id,
        "message_id": message.id,
        "source_reference": source_reference,
        "parsed_count": len(parsed_rows),
        "created_count": len(created_cases),
        "duplicate_count": len(duplicate_cases),
        "skipped_count": len(skipped_rows),
        "created_cases": created_cases,
        "duplicates": duplicate_cases,
        "skipped_rows": skipped_rows,
    }