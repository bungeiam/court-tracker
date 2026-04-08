# app/routes/ui.py
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Case, Inquiry, InquiryBatch, Request as CaseRequest

router = APIRouter(tags=["ui"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


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

    stats = {
        "batch_count": db.query(InquiryBatch).count(),
        "inquiry_count": db.query(Inquiry).count(),
        "case_count": db.query(Case).count(),
        "request_count": db.query(CaseRequest).count(),
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
        },
    )