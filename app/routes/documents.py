from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Case, Request, Document
from app.schemas import DocumentCreate, DocumentResponse, DocumentUpdate

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/case/{case_id}", response_model=DocumentResponse)
def create_document_for_case(case_id: int, payload: DocumentCreate, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if payload.request_id is not None:
        request_item = (
            db.query(Request)
            .filter(Request.id == payload.request_id, Request.case_id == case_id)
            .first()
        )
        if not request_item:
            raise HTTPException(status_code=400, detail="Request not found for this case")

    item = Document(
        case_id=case_id,
        request_id=payload.request_id,
        document_type=payload.document_type,
        title=payload.title,
        description=payload.description,
        source=payload.source,
        sender=payload.sender,
        file_path=payload.file_path,
        mime_type=payload.mime_type,
        public_status=payload.public_status,
        received_date=payload.received_date,
        notes=payload.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/case/{case_id}", response_model=list[DocumentResponse])
def list_case_documents(case_id: int, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    return (
        db.query(Document)
        .filter(Document.case_id == case_id)
        .order_by(Document.id.desc())
        .all()
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, db: Session = Depends(get_db)):
    item = db.query(Document).filter(Document.id == document_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")
    return item


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document(document_id: int, payload: DocumentUpdate, db: Session = Depends(get_db)):
    item = db.query(Document).filter(Document.id == document_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")

    if payload.document_type is not None:
        item.document_type = payload.document_type
    if payload.title is not None:
        item.title = payload.title
    if payload.description is not None:
        item.description = payload.description
    if payload.request_id is not None:
        request_item = (
            db.query(Request)
            .filter(Request.id == payload.request_id, Request.case_id == item.case_id)
            .first()
        )
        if not request_item:
            raise HTTPException(status_code=400, detail="Request not found for this case")
        item.request_id = payload.request_id
    if payload.source is not None:
        item.source = payload.source
    if payload.sender is not None:
        item.sender = payload.sender
    if payload.file_path is not None:
        item.file_path = payload.file_path
    if payload.mime_type is not None:
        item.mime_type = payload.mime_type
    if payload.public_status is not None:
        item.public_status = payload.public_status
    if payload.received_date is not None:
        item.received_date = payload.received_date
    if payload.notes is not None:
        item.notes = payload.notes

    db.commit()
    db.refresh(item)
    return item