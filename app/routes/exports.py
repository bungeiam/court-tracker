from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Case

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/selected-cases")
def export_selected_cases(db: Session = Depends(get_db)):
    cases = (
        db.query(Case)
        .options(
            joinedload(Case.court),
            joinedload(Case.hearing_dates),
            joinedload(Case.parties),
        )
        .filter(Case.selected_for_followup == 1)
        .order_by(Case.id.desc())
        .all()
    )

    result = []

    for case in cases:
        result.append({
            "case_db_id": case.id,
            "court": {
                "name": case.court.name if case.court else None,
                "level": case.court.court_level if case.court else None,
                "city": case.court.city if case.court else None,
            },
            "case": {
                "external_case_id": case.external_case_id,
                "case_type": case.case_type,
                "title": case.title,
                "summary": case.summary,
                "public_status": case.public_status,
                "status": case.status,
            },
            "hearing_dates": [
                {
                    "date": item.hearing_date,
                    "type": item.hearing_type,
                    "notes": item.notes,
                }
                for item in case.hearing_dates
            ],
            "parties": [
                {
                    "role": item.role,
                    "name": item.name,
                    "is_public": item.is_public,
                }
                for item in case.parties
            ],
            "interest": {
                "score": case.interest_score,
                "notes": case.interest_notes,
                "selected_for_followup": bool(case.selected_for_followup),
            },
            "source": {
                "method": case.source_method,
                "reference": case.source_reference,
            },
        })

    return result