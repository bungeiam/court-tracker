from datetime import UTC, datetime
import argparse

from app.database import SessionLocal
from app.models import Inquiry, InquiryBatch
from app.services.email_service import send_email


SENDABLE_FINAL_STATUSES = {"sent", "acknowledged", "responded"}


def resolve_batch(db, batch_id: int | None) -> InquiryBatch | None:
    if batch_id is not None:
        return db.query(InquiryBatch).filter(InquiryBatch.id == batch_id).first()

    return (
        db.query(InquiryBatch)
        .order_by(InquiryBatch.id.desc())
        .first()
    )


def update_batch_status(batch: InquiryBatch) -> None:
    statuses = [inquiry.status for inquiry in batch.inquiries]

    if statuses and all(status in SENDABLE_FINAL_STATUSES for status in statuses):
        batch.status = "sent"
    elif any(status in SENDABLE_FINAL_STATUSES for status in statuses):
        batch.status = "in_progress"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hyväksy ja lähetä yhden inquiry-batchin inquiryt."
    )
    parser.add_argument(
        "--batch-id",
        type=int,
        default=None,
        help="Lähetettävän batchin ID. Jos puuttuu, käytetään uusinta batchia.",
    )
    parser.add_argument(
        "--approve-only",
        action="store_true",
        help="Hyväksyy draft-inquiryt, mutta ei lähetä niitä.",
    )

    args = parser.parse_args()

    db = SessionLocal()

    try:
        batch = resolve_batch(db, args.batch_id)

        if not batch:
            print("Batchia ei löytynyt.")
            return

        inquiries = (
            db.query(Inquiry)
            .filter(Inquiry.batch_id == batch.id)
            .order_by(Inquiry.id.asc())
            .all()
        )

        if not inquiries:
            print(f"Batch {batch.id} ei sisällä inquiryjä.")
            return

        approved_count = 0
        already_approved_count = 0
        sent_count = 0
        skipped_count = 0
        failed_count = 0

        print(f"\nKäsitellään batch {batch.id}: {batch.name}")
        print(f"Inquiryjä yhteensä: {len(inquiries)}")

        for inquiry in inquiries:
            if inquiry.status == "draft":
                inquiry.status = "approved"
                approved_count += 1
            elif inquiry.status == "approved":
                already_approved_count += 1

        db.commit()

        if args.approve_only:
            print(f"Hyväksyttiin {approved_count} draft inquiryä.")
            print(f"Jo valmiiksi approved: {already_approved_count}.")
            return

        for inquiry in inquiries:
            if inquiry.status != "approved":
                skipped_count += 1
                continue

            if not inquiry.recipient_email:
                print(
                    f"- Inquiry {inquiry.id}: skipattu, recipient_email puuttuu."
                )
                skipped_count += 1
                continue

            try:
                send_email(
                    to_email=inquiry.recipient_email,
                    subject=inquiry.subject,
                    body=inquiry.body,
                )
                inquiry.status = "sent"
                inquiry.sent_at = datetime.now(UTC).isoformat()
                sent_count += 1
                print(
                    f"- Inquiry {inquiry.id}: lähetetty -> {inquiry.recipient_email}"
                )
            except Exception as exc:
                failed_count += 1
                print(
                    f"- Inquiry {inquiry.id}: lähetys epäonnistui -> {exc}"
                )

        db.commit()
        db.refresh(batch)
        update_batch_status(batch)
        db.commit()

        print("\nValmis.")
        print(f"Hyväksyttiin uusia: {approved_count}")
        print(f"Jo approved: {already_approved_count}")
        print(f"Lähetetty: {sent_count}")
        print(f"Skipattu: {skipped_count}")
        print(f"Epäonnistui: {failed_count}")
        print(f"Batchin status: {batch.status}")

    finally:
        db.close()


if __name__ == "__main__":
    main()