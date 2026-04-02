from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Court, Inquiry, InquiryBatch
from app.schemas import (
    InquiryBatchCreate,
    InquiryBatchGeneratePayload,
    InquiryBatchResponse,
    InquiryBatchUpdate,
)
from app.services.inquiry_service import build_court_inquiry

router = APIRouter(prefix="/inquiry-batches", tags=["inquiry-batches"])


@router.post("", response_model=InquiryBatchResponse)
def create_inquiry_batch(
    payload: InquiryBatchCreate,
    db: Session = Depends(get_db),
):
    item = InquiryBatch(
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        notes=payload.notes,
        status=payload.status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("", response_model=list[InquiryBatchResponse])
def list_inquiry_batches(db: Session = Depends(get_db)):
    return db.query(InquiryBatch).order_by(InquiryBatch.id.desc()).all()


@router.get("/{batch_id}", response_model=InquiryBatchResponse)
def get_inquiry_batch(batch_id: int, db: Session = Depends(get_db)):
    item = (
        db.query(InquiryBatch)
        .options(joinedload(InquiryBatch.inquiries))
        .filter(InquiryBatch.id == batch_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Inquiry batch not found")
    return item


@router.patch("/{batch_id}", response_model=InquiryBatchResponse)
def update_inquiry_batch(
    batch_id: int,
    payload: InquiryBatchUpdate,
    db: Session = Depends(get_db),
):
    item = db.query(InquiryBatch).filter(InquiryBatch.id == batch_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Inquiry batch not found")

    if payload.name is not None:
        item.name = payload.name
    if payload.start_date is not None:
        item.start_date = payload.start_date
    if payload.end_date is not None:
        item.end_date = payload.end_date
    if payload.notes is not None:
        item.notes = payload.notes
    if payload.status is not None:
        item.status = payload.status

    db.commit()
    db.refresh(item)
    return item


@router.post("/{batch_id}/generate")
def generate_inquiries_for_batch(
    batch_id: int,
    payload: InquiryBatchGeneratePayload,
    db: Session = Depends(get_db),
):
    batch = db.query(InquiryBatch).filter(InquiryBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Inquiry batch not found")

    if not payload.court_ids:
        raise HTTPException(status_code=400, detail="court_ids is required")

    created_items = []
    skipped_items = []

    for court_id in payload.court_ids:
        court = db.query(Court).filter(Court.id == court_id).first()
        if not court:
            skipped_items.append(
                {
                    "court_id": court_id,
                    "status": "skipped",
                    "reason": "Court not found",
                }
            )
            continue

        existing = (
            db.query(Inquiry)
            .filter(Inquiry.batch_id == batch.id, Inquiry.court_id == court.id)
            .first()
        )
        if existing:
            skipped_items.append(
                {
                    "court_id": court.id,
                    "court_name": court.name,
                    "status": "skipped",
                    "reason": "Inquiry already exists for this court in this batch",
                    "inquiry_id": existing.id,
                }
            )
            continue

        generated = build_court_inquiry(
            court=court,
            start_date=batch.start_date,
            end_date=batch.end_date,
        )

        item = Inquiry(
            batch_id=batch.id,
            court_id=court.id,
            recipient_name=generated.get("recipient_name"),
            recipient_email=generated.get("recipient_email"),
            subject=generated["subject"],
            body=generated["body"],
            status=generated.get("status", "draft"),
        )
        db.add(item)
        db.flush()

        created_items.append(
            {
                "inquiry_id": item.id,
                "court_id": court.id,
                "court_name": court.name,
                "recipient_email": item.recipient_email,
                "status": item.status,
            }
        )

    if created_items and batch.status == "draft":
        batch.status = "generated"

    db.commit()

    return {
        "batch_id": batch.id,
        "created_count": len(created_items),
        "skipped_count": len(skipped_items),
        "created": created_items,
        "skipped": skipped_items,
    }