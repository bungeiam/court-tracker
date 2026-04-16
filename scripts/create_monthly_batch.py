from datetime import date
from calendar import monthrange

from app.database import SessionLocal
from app.models import Court, InquiryBatch, Inquiry
from app.services.inquiry_service import build_court_inquiry


def get_month_range(year: int, month: int):
    start_date = date(year, month, 1)
    last_day = monthrange(year, month)[1]
    end_date = date(year, month, last_day)
    return start_date.isoformat(), end_date.isoformat()


def main(year: int, month: int):
    db = SessionLocal()

    try:
        start_date, end_date = get_month_range(year, month)

        batch_name = f"Käräjäoikeudet {year}-{str(month).zfill(2)}"

        print(f"\nLuodaan batch: {batch_name}")
        print(f"Aikaväli: {start_date} – {end_date}")

        # 1. luo batch
        batch = InquiryBatch(
            name=batch_name,
            start_date=start_date,
            end_date=end_date,
            status="draft",
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)

        # 2. hae aktiiviset käräjäoikeudet
        courts = (
            db.query(Court)
            .filter(Court.active == True)
            .filter(Court.court_level == "käräjäoikeus")
            .all()
        )

        print(f"Courtteja mukana: {len(courts)}")

        created = 0
        skipped = 0

        # 3. generoi inquiryt
        for court in courts:
            existing = (
                db.query(Inquiry)
                .filter(Inquiry.batch_id == batch.id)
                .filter(Inquiry.court_id == court.id)
                .first()
            )

            if existing:
                skipped += 1
                continue

            generated = build_court_inquiry(
                court=court,
                start_date=start_date,
                end_date=end_date,
            )

            inquiry = Inquiry(
                batch_id=batch.id,
                court_id=court.id,
                recipient_name=generated.get("recipient_name"),
                recipient_email=generated.get("recipient_email"),
                subject=generated["subject"],
                body=generated["body"],
                status=generated.get("status", "draft"),
            )

            db.add(inquiry)
            created += 1

        if created > 0:
            batch.status = "generated"

        db.commit()

        print(f"\nBatch ID: {batch.id}")
        print(f"Luotiin {created} inquiryä")
        print(f"Skipattiin {skipped}")

    finally:
        db.close()


if __name__ == "__main__":
    main(2026, 4)