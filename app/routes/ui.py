# app/routes/ui.py
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
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
from app.routes.inquiries import (
    CreateCasesPayload,
    approve_inquiry as approve_inquiry_api,
    create_cases_from_inquiry as create_cases_from_inquiry_api,
    send_single_inquiry as send_single_inquiry_api,
)
from app.routes.requests import (
    approve_request as approve_request_api,
    send_single_request as send_single_request_api,
)

router = APIRouter(tags=["ui"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def _not_found(entity_name: str):
    raise HTTPException(status_code=404, detail=f"{entity_name} not found")


def _redirect_with_message(
    path: str,
    *,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    params: dict[str, str] = {}
    if success:
        params["success"] = success
    if error:
        params["error"] = error

    target = path
    if params:
        target = f"{path}?{urlencode(params)}"

    return RedirectResponse(url=target, status_code=303)


def _build_template_context(request: Request, extra: dict) -> dict:
    context = {
        "request": request,
        "success_message": request.query_params.get("success"),
        "error_message": request.query_params.get("error"),
    }
    context.update(extra)
    return context


def _has_response_message(inquiry: Inquiry) -> bool:
    return any(message.message_type == "response" for message in (inquiry.messages or []))


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
        _build_template_context(
            request,
            {
                "page_title": "Dashboard",
                "stats": stats,
                "latest_batches": latest_batches,
                "latest_inquiries": latest_inquiries,
                "latest_cases": latest_cases,
                "latest_requests": latest_requests,
                "latest_documents": latest_documents,
            },
        ),
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
        _build_template_context(
            request,
            {
                "page_title": f"Inquiry batch #{batch.id}",
                "batch": batch,
                "inquiries": inquiries,
            },
        ),
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
    can_create_cases = _has_response_message(inquiry)

    return templates.TemplateResponse(
        request,
        "inquiry_detail.html",
        _build_template_context(
            request,
            {
                "page_title": f"Inquiry #{inquiry.id}",
                "inquiry": inquiry,
                "messages": messages,
                "can_create_cases": can_create_cases,
            },
        ),
    )


@router.post("/ui/inquiries/{inquiry_id}/approve")
def approve_inquiry_ui(
    inquiry_id: int,
    db: Session = Depends(get_db),
):
    detail_path = f"/ui/inquiries/{inquiry_id}"

    try:
        approve_inquiry_api(inquiry_id=inquiry_id, db=db)
    except HTTPException as exc:
        return _redirect_with_message(detail_path, error=exc.detail)

    return _redirect_with_message(detail_path, success="Inquiry hyväksyttiin.")


@router.post("/ui/inquiries/{inquiry_id}/send")
def send_inquiry_ui(
    inquiry_id: int,
    db: Session = Depends(get_db),
):
    detail_path = f"/ui/inquiries/{inquiry_id}"

    try:
        send_single_inquiry_api(inquiry_id=inquiry_id, db=db)
    except HTTPException as exc:
        return _redirect_with_message(detail_path, error=exc.detail)

    return _redirect_with_message(detail_path, success="Inquiry lähetettiin.")


@router.post("/ui/inquiries/{inquiry_id}/create-cases")
def create_cases_from_inquiry_ui(
    inquiry_id: int,
    db: Session = Depends(get_db),
):
    detail_path = f"/ui/inquiries/{inquiry_id}"

    try:
        result = create_cases_from_inquiry_api(
            inquiry_id=inquiry_id,
            payload=CreateCasesPayload(),
            db=db,
        )
    except HTTPException as exc:
        return _redirect_with_message(detail_path, error=exc.detail)

    created_count = result.get("created_count", 0)
    duplicate_count = result.get("duplicate_count", result.get("skipped_duplicates_count", 0))
    skipped_count = result.get("skipped_count", 0)

    success_parts = [
        f"Case-luonti valmis. Luotiin {created_count} casea.",
        f"Duplikaatteina ohitettiin {duplicate_count}.",
    ]
    if skipped_count:
        success_parts.append(f"Lisäksi parsinnassa ohitettiin {skipped_count} riviä.")

    return _redirect_with_message(detail_path, success=" ".join(success_parts))


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
        _build_template_context(
            request,
            {
                "page_title": f"Case #{case.id}",
                "case_item": case,
                "hearing_dates": hearing_dates,
                "parties": parties,
                "requests": requests,
                "documents": documents,
            },
        ),
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
        _build_template_context(
            request,
            {
                "page_title": f"Request #{request_item.id}",
                "request_item": request_item,
                "documents": documents,
            },
        ),
    )


@router.post("/ui/requests/{request_id}/approve")
def approve_request_ui(
    request_id: int,
    db: Session = Depends(get_db),
):
    detail_path = f"/ui/requests/{request_id}"

    try:
        approve_request_api(request_id=request_id, db=db)
    except HTTPException as exc:
        return _redirect_with_message(detail_path, error=exc.detail)

    return _redirect_with_message(detail_path, success="Request hyväksyttiin.")


@router.post("/ui/requests/{request_id}/send")
def send_request_ui(
    request_id: int,
    db: Session = Depends(get_db),
):
    detail_path = f"/ui/requests/{request_id}"

    try:
        send_single_request_api(request_id=request_id, db=db)
    except HTTPException as exc:
        return _redirect_with_message(detail_path, error=exc.detail)

    return _redirect_with_message(detail_path, success="Request lähetettiin.")

    
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
        _build_template_context(
            request,
            {
                "page_title": f"Document #{document.id}",
                "document_item": document,
            },
        ),
    )