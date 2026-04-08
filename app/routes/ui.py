from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import (
    Case,
    Document,
    Inquiry,
    InquiryBatch,
    Request as CaseRequest,
)

router = APIRouter(tags=["ui"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _not_found(entity_name: str):
    raise HTTPException(status_code=404, detail=f"{entity_name} not found")


@router.get("/ui", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    latest_batches = (
        db.query(InquiryBatch)
        .order_by(InquiryBatch.id.desc())
        .limit(8)
        .all()
    )

    latest_inquiries = (
        db.query(Inquiry)
        .options(
            joinedload(Inquiry.court),
            joinedload(Inquiry.batch),
        )
        .order_by(Inquiry.id.desc())
        .limit(8)
        .all()
    )

    latest_cases = (
        db.query(Case)
        .options(joinedload(Case.court))
        .order_by(Case.id.desc())
        .limit(8)
        .all()
    )

    latest_requests = (
        db.query(CaseRequest)
        .options(joinedload(CaseRequest.case))
        .order_by(CaseRequest.id.desc())
        .limit(8)
        .all()
    )

    latest_documents = (
        db.query(Document)
        .options(
            joinedload(Document.case),
            joinedload(Document.request),
        )
        .order_by(Document.id.desc())
        .limit(8)
        .all()
    )

    stats = {
        "batch_count": db.query(InquiryBatch).count(),
        "inquiry_count": db.query(Inquiry).count(),
        "case_count": db.query(Case).count(),
        "request_count": db.query(CaseRequest).count(),
        "document_count": db.query(Document).count(),
    }

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "page_title": "Dashboard",
            "stats": stats,
            "latest_batches": latest_batches,
            "latest_inquiries": latest_inquiries,
            "latest_cases": latest_cases,
            "latest_requests": latest_requests,
            "latest_documents": latest_documents,
        },
    )


@router.get("/ui/inquiry-batches/{batch_id}", response_class=HTMLResponse)
def inquiry_batch_detail(
    batch_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    batch = (
        db.query(InquiryBatch)
        .options(
            joinedload(InquiryBatch.inquiries).joinedload(Inquiry.court),
        )
        .filter(InquiryBatch.id == batch_id)
        .first()
    )
    if not batch:
        _not_found("Inquiry batch")

    inquiries = sorted(batch.inquiries or [], key=lambda item: item.id, reverse=True)

    return templates.TemplateResponse(
        request,
        "inquiry_batch_detail.html",
        {
            "page_title": f"Inquiry batch #{batch.id}",
            "batch": batch,
            "inquiries": inquiries,
        },
    )


@router.get("/ui/inquiries/{inquiry_id}", response_class=HTMLResponse)
def inquiry_detail(
    inquiry_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    inquiry = (
        db.query(Inquiry)
        .options(
            joinedload(Inquiry.court),
            joinedload(Inquiry.batch),
            joinedload(Inquiry.messages),
        )
        .filter(Inquiry.id == inquiry_id)
        .first()
    )
    if not inquiry:
        _not_found("Inquiry")

    messages = sorted(inquiry.messages or [], key=lambda item: item.id, reverse=True)

    return templates.TemplateResponse(
        request,
        "inquiry_detail.html",
        {
            "page_title": f"Inquiry #{inquiry.id}",
            "inquiry": inquiry,
            "messages": messages,
        },
    )


@router.get("/ui/cases/{case_id}", response_class=HTMLResponse)
def case_detail(
    case_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    case = (
        db.query(Case)
        .options(
            joinedload(Case.court),
            joinedload(Case.hearing_dates),
            joinedload(Case.parties),
            joinedload(Case.requests),
            joinedload(Case.documents),
        )
        .filter(Case.id == case_id)
        .first()
    )
    if not case:
        _not_found("Case")

    hearing_dates = sorted(
        case.hearing_dates or [],
        key=lambda item: ((item.hearing_date or ""), item.id),
    )
    parties = sorted(case.parties or [], key=lambda item: (item.role or "", item.name or ""))
    requests = sorted(case.requests or [], key=lambda item: item.id, reverse=True)
    documents = sorted(case.documents or [], key=lambda item: item.id, reverse=True)

    return templates.TemplateResponse(
        request,
        "case_detail.html",
        {
            "page_title": f"Case #{case.id}",
            "case_item": case,
            "hearing_dates": hearing_dates,
            "parties": parties,
            "requests": requests,
            "documents": documents,
        },
    )


@router.get("/ui/requests/{request_id}", response_class=HTMLResponse)
def request_detail(
    request_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    request_item = (
        db.query(CaseRequest)
        .options(
            joinedload(CaseRequest.case).joinedload(Case.court),
            joinedload(CaseRequest.documents),
        )
        .filter(CaseRequest.id == request_id)
        .first()
    )
    if not request_item:
        _not_found("Request")

    documents = sorted(request_item.documents or [], key=lambda item: item.id, reverse=True)

    return templates.TemplateResponse(
        request,
        "request_detail.html",
        {
            "page_title": f"Request #{request_item.id}",
            "request_item": request_item,
            "documents": documents,
        },
    )


@router.get("/ui/documents/{document_id}", response_class=HTMLResponse)
def document_detail(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document)
        .options(
            joinedload(Document.case).joinedload(Case.court),
            joinedload(Document.request),
        )
        .filter(Document.id == document_id)
        .first()
    )
    if not document:
        _not_found("Document")

    return templates.TemplateResponse(
        request,
        "document_detail.html",
        {
            "page_title": f"Document #{document.id}",
            "document_item": document,
        },
    )