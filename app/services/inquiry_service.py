from app.models import Court


def build_court_inquiry(court: Court, start_date: str, end_date: str) -> dict:
    court_name = court.name if court else "Käräjäoikeus"
    court_email = court.email if court else None

    subject = f"Tiedustelu rikosasioiden käsittelyistä ajalla {start_date}–{end_date}"

    body = f"""Hei,

Pyydän tietoa {court_name}ssa ajalla {start_date}–{end_date} käsiteltävistä tai käsitellyistä rikosasioista.

Pyydän ilmoittamaan kustakin asiasta mahdollisuuksien mukaan ainakin seuraavat tiedot:
- käsittelypäivä tai käsittelypäivät
- diaarinumero
- asianimike / syytenimike
- vastaaja tai vastaajat siltä osin kuin tieto on julkinen

Tiedot voi toimittaa sähköpostitse tähän osoitteeseen.

Ystävällisin terveisin
[OMA NIMI]
[OMA SÄHKÖPOSTI]
[OMA PUHELIN]
"""

    return {
        "recipient_name": court_name,
        "recipient_email": court_email,
        "subject": subject,
        "body": body,
        "status": "draft",
    }