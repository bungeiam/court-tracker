from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Court
from app.schemas import CourtCreate, CourtResponse

router = APIRouter(prefix="/courts", tags=["courts"])


@router.post("", response_model=CourtResponse)
def create_court(court: CourtCreate, db: Session = Depends(get_db)):
    db_court = Court(
        name=court.name,
        court_level=court.court_level,
        city=court.city,
        email=court.email,
        notes=court.notes
    )
    db.add(db_court)
    db.commit()
    db.refresh(db_court)
    return db_court


@router.get("", response_model=list[CourtResponse])
def list_courts(db: Session = Depends(get_db)):
    return db.query(Court).order_by(Court.name.asc()).all()