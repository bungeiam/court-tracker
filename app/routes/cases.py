# app/routes/cases.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Case, Court, HearingDate, Party
from app.schemas import (
    CaseCreate,
    CaseDetailResponse,
    CaseResponse,
    FollowUpCaseWithoutRequestListResponse,
    FollowUpCaseWithoutRequestResponse,
    HearingDateCreate,
    HearingDateResponse,
    PartyCreate,
    PartyResponse,
)

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseUpdateSelection(BaseModel):
    selected_for_followup: int
    interest_score: int | None = None
    interest_notes: str | None = None
    status: str | None = None


@router.post("", response_model=CaseResponse)
def create_case(case: CaseCreate, db: Session = Depends(get_db)):
    court = db.query(Court).filter(Court.id == case.court_id).first()
    if not court:
        raise HTTPException(status_code=404, detail="Court not found")

    db_case = Case(
        court_id=case.court_id,
        external_case_id=case.external_case_id,
        case_type=case.case_type,
        title=case.title,
        summary=case.summary,
        public_status=case.public_status,
        source_method=case.source_method,
        source_reference=case.source_reference,
        raw_text=case.raw_text,
        interest_score=case.interest_score,
        interest_notes=case.interest_notes,
        selected_for_followup=case.selected_for_followup,
        status=case.status,
    )
    db.add(db_case)
    db.commit()
    db.refresh(db_case)
    return db_case


@router.get("", response_model=list[CaseResponse])
def list_cases(db: Session = Depends(get_db)):
    return db.query(Case).order_by(Case.id.desc()).all()


@router.get("/tracking/missing-requests", response_model=FollowUpCaseWithoutRequestListResponse)
def list_followup_cases_missing_requests(db: Session = Depends(get_db)):
    cases = (
        db.query(Case)
        .options(
            joinedload(Case.court),
            joinedload(Case.hearing_dates),
            joinedload(Case.requests),
            joinedload(Case.documents),
        )
        .filter(Case.selected_for_followup == 1)
        .order_by(Case.id.desc())
        .all()
    )

    result_items: list[FollowUpCaseWithoutRequestResponse] = []

    for case in cases:
        request_count = len(case.requests or [])
        if request_count > 0:
            continue

        sorted_hearing_dates = sorted(
            [item.hearing_date for item in (case.hearing_dates or []) if item.hearing_date]
        )
        first_hearing_date = sorted_hearing_dates[0] if sorted_hearing_dates else None

        result_items.append(
            FollowUpCaseWithoutRequestResponse(
                case_id=case.id,
                court_id=case.court_id,
                external_case_id=case.external_case_id,
                case_type=case.case_type,
                title=case.title,
                case_status=case.status,
                interest_score=case.interest_score,
                interest_notes=case.interest_notes,
                selected_for_followup=bool(case.selected_for_followup),
                request_count=request_count,
                document_count=len(case.documents or []),
                first_hearing_date=first_hearing_date,
                court_name=case.court.name if case.court else None,
                court_city=case.court.city if case.court else None,
            )
        )

    return FollowUpCaseWithoutRequestListResponse(
        count=len(result_items),
        items=result_items,
    )


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(case_id: int, db: Session = Depends(get_db)):
    db_case = (
        db.query(Case)
        .options(
            joinedload(Case.hearing_dates),
            joinedload(Case.parties),
            joinedload(Case.requests),
        )
        .filter(Case.id == case_id)
        .first()
    )
    if not db_case:
        raise HTTPException(status_code=404, detail="Case not found")
    return db_case


@router.patch("/{case_id}/selection", response_model=CaseResponse)
def update_case_selection(case_id: int, payload: CaseUpdateSelection, db: Session = Depends(get_db)):
    db_case = db.query(Case).filter(Case.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="Case not found")

    db_case.selected_for_followup = payload.selected_for_followup

    if payload.interest_score is not None:
        db_case.interest_score = payload.interest_score
    if payload.interest_notes is not None:
        db_case.interest_notes = payload.interest_notes
    if payload.status is not None:
        db_case.status = payload.status

    db.commit()
    db.refresh(db_case)
    return db_case


@router.post("/{case_id}/hearing-dates", response_model=HearingDateResponse)
def create_hearing_date(case_id: int, payload: HearingDateCreate, db: Session = Depends(get_db)):
    db_case = db.query(Case).filter(Case.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="Case not found")

    item = HearingDate(
        case_id=case_id,
        hearing_date=payload.hearing_date,
        hearing_type=payload.hearing_type,
        notes=payload.notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.post("/{case_id}/parties", response_model=PartyResponse)
def create_party(case_id: int, payload: PartyCreate, db: Session = Depends(get_db)):
    db_case = db.query(Case).filter(Case.id == case_id).first()
    if not db_case:
        raise HTTPException(status_code=404, detail="Case not found")

    item = Party(
        case_id=case_id,
        role=payload.role,
        name=payload.name,
        is_public=payload.is_public,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item