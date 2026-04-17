from collections import Counter
from pathlib import Path
import re
from types import SimpleNamespace
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
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
from app.routes.documents import (
    delete_document as delete_document_api,
    upload_document_for_case as upload_document_for_case_api,
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

INQUIRY_SOURCE_REFERENCE_RE = re.compile(r"^Inquiry (\d+) /")


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
        "status_badge_class": _status_badge_class,
        "followup_badge_class": _followup_badge_class,
    }
    context.update(extra)
    return context


def _status_badge_class(status: str | None) -> str:
    mapping = {
        "draft": "text-bg-secondary",
        "approved": "text-bg-primary",
        "sent": "text-bg-info",
        "acknowledged": "text-bg-warning",
        "responded": "text-bg-success",
        "completed": "text-bg-success",
        "in_progress": "text-bg-warning",
        "new": "text-bg-secondary",
        "replied": "text-bg-success",
    }
    return mapping.get((status or "").strip().lower(), "text-bg-secondary")


def _followup_badge_class(selected: int | bool | None) -> str:
    return "text-bg-warning" if bool(selected) else "text-bg-light"


def _has_response_message(inquiry: Inquiry) -> bool:
    return any(message.message_type == "response" for message in (inquiry.messages or []))


def _normalize_status_filter(value: str | None) -> str:
    normalized = (value or "all").strip().lower()
    return normalized or "all"


def _normalize_followup_filter(value: str | None) -> str:
    normalized = (value or "all").strip().lower()
    if normalized not in {"all", "yes", "no"}:
        return "all"
    return normalized


def _normalize_case_sort(value: str | None) -> str:
    normalized = (value or "interest_desc").strip().lower()
    if normalized not in {"newest", "interest_desc", "interest_asc"}:
        return "interest_desc"
    return normalized


def _count_by_status(items: list) -> dict[str, int]:
    counts = Counter((item.status or "unknown") for item in items)
    return dict(sorted(counts.items(), key=lambda pair: pair[0]))


def _get_inquiry_ids_with_created_cases(db: Session) -> set[int]:
    inquiry_ids: set[int] = set()

    rows = (
        db.query(Case.source_reference)
        .filter(Case.source_method == "inquiry_response")
        .all()
    )

    for row in rows:
        source_reference = row[0]
        if not source_reference:
            continue

        match = INQUIRY_SOURCE_REFERENCE_RE.match(source_reference)
        if match:
            inquiry_ids.add(int(match.group(1)))

    return inquiry_ids


def _get_inquiries(
    db: Session,
    *,
    status_filter: str = "all",
    limit: int | None = None,
) -> list[Inquiry]:
    query = (
        db.query(Inquiry)
        .options(
            joinedload(Inquiry.court),
            joinedload(Inquiry.batch),
            joinedload(Inquiry.messages),
        )
        .order_by(Inquiry.id.desc())
    )

    if status_filter != "all":
        query = query.filter(Inquiry.status == status_filter)

    if limit is not None:
        query = query.limit(limit)

    return query.all()


def _build_inquiry_rows(db: Session, inquiries: list[Inquiry]) -> list[SimpleNamespace]:
    inquiry_ids_with_created_cases = _get_inquiry_ids_with_created_cases(db)
    rows: list[SimpleNamespace] = []

    for inquiry in inquiries:
        has_response = _has_response_message(inquiry)
        has_created_cases = inquiry.id in inquiry_ids_with_created_cases

        rows.append(
            SimpleNamespace(
                inquiry=inquiry,
                has_response=has_response,
                has_created_cases=has_created_cases,
                can_create_cases=has_response and not has_created_cases,
            )
        )

    return rows


def _get_cases(
    db: Session,
    *,
    followup_filter: str = "all",
    sort_by: str = "interest_desc",
    limit: int | None = None,
) -> list[Case]:
    query = (
        db.query(Case)
        .options(
            joinedload(Case.court),
            joinedload(Case.requests),
            joinedload(Case.documents),
            joinedload(Case.hearing_dates),
        )
        .order_by(Case.id.desc())
    )

    if followup_filter == "yes":
        query = query.filter(Case.selected_for_followup == 1)
    elif followup_filter == "no":
        query = query.filter(Case.selected_for_followup == 0)

    items = query.all()

    if sort_by == "interest_asc":
        items = sorted(
            items,
            key=lambda item: (
                item.interest_score is None,
                item.interest_score if item.interest_score is not None else 999999,
                -item.id,
            ),
        )
    elif sort_by == "interest_desc":
        items = sorted(
            items,
            key=lambda item: (
                item.interest_score is None,
                -(item.interest_score if item.interest_score is not None else -1),
                -item.id,
            ),
        )
    else:
        items = sorted(items, key=lambda item: item.id, reverse=True)

    if limit is not None:
        items = items[:limit]

    return items


def _build_case_rows(cases: list[Case]) -> list[SimpleNamespace]:
    rows: list[SimpleNamespace] = []

    for case_item in cases:
        hearing_dates = sorted(
            [item.hearing_date for item in (case_item.hearing_dates or []) if item.hearing_date]
        )
        first_hearing_date = hearing_dates[0] if hearing_dates else None

        rows.append(
            SimpleNamespace(
                case_item=case_item,
                request_count=len(case_item.requests or []),
                document_count=len(case_item.documents or []),
                first_hearing_date=first_hearing_date,
            )
        )

    return rows


def _get_requests(
    db: Session,
    *,
    status_filter: str = "all",
    limit: int | None = None,
) -> list[CaseRequest]:
    query = (
        db.query(CaseRequest)
        .options(
            joinedload(CaseRequest.case).joinedload(Case.court),
            joinedload(CaseRequest.documents),
        )
        .order_by(CaseRequest.id.desc())
    )

    if status_filter != "all":
        query = query.filter(CaseRequest.status == status_filter)

    if limit is not None:
        query = query.limit(limit)

    return query.all()


def _build_request_rows(items: list[CaseRequest]) -> list[SimpleNamespace]:
    rows: list[SimpleNamespace] = []

    for item in items:
        document_count = len(item.documents or [])
        rows.append(
            SimpleNamespace(
                request_item=item,
                document_count=document_count,
                has_document=document_count > 0,
            )
        )

    return rows


def _get_followup_cases_missing_requests(db: Session, limit: int = 10) -> list[SimpleNamespace]:
    items = _get_cases(
        db,
        followup_filter="yes",
        sort_by="interest_desc",
        limit=None,
    )
    filtered = [item for item in items if len(item.requests or []) == 0]
    return _build_case_rows(filtered[:limit])


def _get_requests_missing_documents(db: Session, limit: int = 10) -> list[SimpleNamespace]:
    items = _get_requests(db, status_filter="all", limit=None)
    filtered = [item for item in items if len(item.documents or []) == 0]
    return _build_request_rows(filtered[:limit])


def _get_inquiries_pending_case_creation(db: Session, limit: int = 10) -> list[SimpleNamespace]:
    items = _get_inquiries(db, status_filter="all", limit=None)
    rows = _build_inquiry_rows(db, items)
    filtered = [row for row in rows if row.can_create_cases]
    return filtered[:limit]


@router.get("/ui", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    inquiry_status = _normalize_status_filter(request.query_params.get("inquiry_status"))
    request_status = _normalize_status_filter(request.query_params.get("request_status"))
    case_followup = _normalize_followup_filter(request.query_params.get("case_followup"))
    case_sort = _normalize_case_sort(request.query_params.get("case_sort"))

    latest_batches = (
        db.query(InquiryBatch)
        .order_by(InquiryBatch.id.desc())
        .limit(6)
        .all()
    )

    inquiry_items = _get_inquiries(db, status_filter=inquiry_status, limit=10)
    case_items = _get_cases(
        db,
        followup_filter=case_followup,
        sort_by=case_sort,
        limit=10,
    )
    request_items = _get_requests(db, status_filter=request_status, limit=10)

    inquiry_rows = _build_inquiry_rows(db, inquiry_items)
    case_rows = _build_case_rows(case_items)
    request_rows = _build_request_rows(request_items)

    stats = {
        "batch_count": db.query(InquiryBatch).count(),
        "inquiry_count": db.query(Inquiry).count(),
        "open_inquiry_count": db.query(Inquiry).filter(Inquiry.status != "responded").count(),
        "case_count": db.query(Case).count(),
        "followup_case_count": db.query(Case).filter(Case.selected_for_followup == 1).count(),
        "request_count": db.query(CaseRequest).count(),
        "open_request_count": db.query(CaseRequest).filter(CaseRequest.status != "replied").count(),
        "document_count": db.query(Document).count(),
    }

    work_queues = {
        "followup_cases_missing_requests": _get_followup_cases_missing_requests(db, limit=10),
        "requests_missing_documents": _get_requests_missing_documents(db, limit=10),
        "inquiries_pending_case_creation": _get_inquiries_pending_case_creation(db, limit=10),
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
                "inquiry_rows": inquiry_rows,
                "case_rows": case_rows,
                "request_rows": request_rows,
                "work_queues": work_queues,
                "active_filters": {
                    "inquiry_status": inquiry_status,
                    "request_status": request_status,
                    "case_followup": case_followup,
                    "case_sort": case_sort,
                },
            },
        ),
    )


@router.get("/ui/inquiries", response_class=HTMLResponse)
def inquiry_list(request: Request, db: Session = Depends(get_db)):
    status_filter = _normalize_status_filter(request.query_params.get("status"))
    items = _get_inquiries(db, status_filter=status_filter, limit=None)
    rows = _build_inquiry_rows(db, items)

    all_items = _get_inquiries(db, status_filter="all", limit=None)

    return templates.TemplateResponse(
        request,
        "inquiries_list.html",
        _build_template_context(
            request,
            {
                "page_title": "Inquiries",
                "rows": rows,
                "status_filter": status_filter,
                "status_counts": _count_by_status(all_items),
                "total_count": len(all_items),
            },
        ),
    )


@router.get("/ui/cases", response_class=HTMLResponse)
def case_list(request: Request, db: Session = Depends(get_db)):
    followup_filter = _normalize_followup_filter(request.query_params.get("followup"))
    sort_by = _normalize_case_sort(request.query_params.get("sort"))

    items = _get_cases(
        db,
        followup_filter=followup_filter,
        sort_by=sort_by,
        limit=None,
    )
    rows = _build_case_rows(items)

    total_count = db.query(Case).count()
    followup_count = db.query(Case).filter(Case.selected_for_followup == 1).count()
    non_followup_count = db.query(Case).filter(Case.selected_for_followup == 0).count()

    return templates.TemplateResponse(
        request,
        "cases_list.html",
        _build_template_context(
            request,
            {
                "page_title": "Caset",
                "rows": rows,
                "followup_filter": followup_filter,
                "sort_by": sort_by,
                "total_count": total_count,
                "followup_count": followup_count,
                "non_followup_count": non_followup_count,
            },
        ),
    )


@router.get("/ui/requests", response_class=HTMLResponse)
def request_list(request: Request, db: Session = Depends(get_db)):
    status_filter = _normalize_status_filter(request.query_params.get("status"))
    items = _get_requests(db, status_filter=status_filter, limit=None)
    rows = _build_request_rows(items)

    all_items = _get_requests(db, status_filter="all", limit=None)

    return templates.TemplateResponse(
        request,
        "requests_list.html",
        _build_template_context(
            request,
            {
                "page_title": "Requestit",
                "rows": rows,
                "status_filter": status_filter,
                "status_counts": _count_by_status(all_items),
                "total_count": len(all_items),
                "missing_document_count": len([item for item in all_items if len(item.documents or []) == 0]),
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
                "upload_request_options": requests,
            },
        ),
    )


@router.post("/ui/cases/{case_id}/documents/upload")
def upload_case_document_ui(
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
    detail_path = f"/ui/cases/{case_id}"

    try:
        upload_document_for_case_api(
            case_id=case_id,
            document_type=document_type,
            title=title,
            description=description,
            request_id=request_id,
            source=source,
            sender=sender,
            public_status=public_status,
            received_date=received_date,
            notes=notes,
            uploaded_file=uploaded_file,
            db=db,
        )
    except HTTPException as exc:
        return _redirect_with_message(detail_path, error=exc.detail)

    return _redirect_with_message(detail_path, success="Dokumentti ladattiin onnistuneesti.")


@router.post("/ui/documents/{document_id}/delete")
def delete_document_ui(
    document_id: int,
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return _redirect_with_message("/ui", error="Document not found")

    case_id = document.case_id

    try:
        delete_document_api(document_id=document_id, db=db)
    except HTTPException as exc:
        return _redirect_with_message(f"/ui/cases/{case_id}", error=exc.detail)

    return _redirect_with_message(f"/ui/cases/{case_id}", success="Dokumentti poistettiin.")


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
                "can_delete_document": True,
            },
        ),
    )

@router.post("/ui/inquiry-batches/{batch_id}/approve-all")
def approve_batch_ui(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(InquiryBatch).filter(InquiryBatch.id == batch_id).first()
    if not batch:
        return _redirect_with_message("/ui", error="Batch not found")

    count = 0

    for inquiry in batch.inquiries:
        if inquiry.status == "draft":
            inquiry.status = "approved"
            count += 1

    db.commit()

    return _redirect_with_message(
        f"/ui/inquiry-batches/{batch_id}",
        success=f"{count} inquiryä hyväksyttiin.",
    )


@router.post("/ui/inquiry-batches/{batch_id}/send")
def send_batch_ui(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(InquiryBatch).filter(InquiryBatch.id == batch_id).first()
    if not batch:
        return _redirect_with_message("/ui", error="Batch not found")

    try:
        # käytetään olemassa olevaa endpointtia
        from app.routes.inquiries import send_all_approved_inquiries
        send_all_approved_inquiries(db=db)
    except Exception as e:
        return _redirect_with_message(
            f"/ui/inquiry-batches/{batch_id}",
            error=f"Lähetys epäonnistui: {str(e)}",
        )

    return _redirect_with_message(
        f"/ui/inquiry-batches/{batch_id}",
        success="Batchin inquiryt lähetettiin.",
    )