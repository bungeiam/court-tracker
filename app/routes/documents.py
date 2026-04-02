from pathlib import Path
import shutil

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
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


@router.post("/case/{case_id}/upload", response_model=DocumentResponse)
def upload_document_for_case(
    case_id: int,
    document_type: str = Form(...),
    title: str = Form(...),
    description: str | None = Form(None),
    request_id: str | None = Form(None),
    source: str | None = Form(None),
    sender: str | None = Form(None),
    public_status: str | None = Form(None),
    received_date: str | None = Form(None),
    notes: str | None = Form(None),
    uploaded_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    normalized_request_id: int | None = None
    if request_id is not None and str(request_id).strip() != "":
        try:
            normalized_request_id = int(str(request_id).strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="request_id must be an integer")

        request_item = (
            db.query(Request)
            .filter(Request.id == normalized_request_id, Request.case_id == case_id)
            .first()
        )
        if not request_item:
            raise HTTPException(status_code=400, detail="Request not found for this case")

    original_filename = uploaded_file.filename or "file"
    safe_filename = Path(original_filename).name

    storage_root = Path("storage")
    case_dir = storage_root / f"case_{case_id}"
    case_dir.mkdir(parents=True, exist_ok=True)

    target_path = case_dir / safe_filename

    if target_path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"File already exists on disk: {safe_filename}",
        )

    with target_path.open("wb") as buffer:
        shutil.copyfileobj(uploaded_file.file, buffer)

    item = Document(
        case_id=case_id,
        request_id=normalized_request_id,
        document_type=document_type,
        title=title,
        description=description,
        source=source,
        sender=sender,
        file_path=str(target_path).replace("\\", "/"),
        mime_type=uploaded_file.content_type,
        public_status=public_status,
        received_date=received_date,
        notes=notes,
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


@router.get("/{document_id}/download")
def download_document(document_id: int, db: Session = Depends(get_db)):
    item = db.query(Document).filter(Document.id == document_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")

    if not item.file_path:
        raise HTTPException(status_code=400, detail="Document has no file_path")

    file_path = Path(item.file_path)
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk")

    media_type = item.mime_type or "application/octet-stream"
    filename = file_path.name

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename,
    )


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