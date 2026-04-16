from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Court
from app.schemas import CourtCreate, CourtResponse, CourtUpdate

router = APIRouter(prefix="/courts", tags=["courts"])


@router.post("", response_model=CourtResponse)
def create_court(court: CourtCreate, db: Session = Depends(get_db)):
    db_court = Court(
        name=court.name,
        court_level=court.court_level,
        city=court.city,
        email=court.email,
        notes=court.notes,
        active=court.active,
    )
    db.add(db_court)
    db.commit()
    db.refresh(db_court)
    return db_court


@router.get("", response_model=list[CourtResponse])
def list_courts(db: Session = Depends(get_db)):
    return db.query(Court).order_by(Court.name.asc()).all()


@router.patch("/{court_id}", response_model=CourtResponse)
def update_court(court_id: int, payload: CourtUpdate, db: Session = Depends(get_db)):
    court = db.query(Court).filter(Court.id == court_id).first()

    if not court:
        raise HTTPException(status_code=404, detail="Court not found")

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(court, field, value)

    db.commit()
    db.refresh(court)
    return court