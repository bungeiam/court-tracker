from app.config import SENDER_EMAIL, SENDER_NAME, SENDER_PHONE
from app.models import Court, Inquiry, InquiryMessage


def build_court_inquiry(court: Court, start_date: str, end_date: str) -> dict:
    court_name = court.name if court else "Käräjäoikeus"
    court_email = court.email if court else None
    subject = f"{court_name} - rikosasioiden käsittelytiedot {start_date}–{end_date}"
    body = f"""Hyvä vastaanottaja,

Tämä on viranomaisten toiminnan julkisuudesta annetun lain (621/1999) 13 §:ään ja 16 §:ään sekä oikeudenkäynnin julkisuudesta yleisissä tuomioistuimissa annetun lain (370/2007) 4 §:ään perustuva tietopyyntö.

Pyydän saada tiedot ajalla {start_date}–{end_date} käsitellyistä tai käsiteltäväksi merkityistä rikosasioista {court_name}. Pyydän seuraavat julkiset tiedot:
- käsittelypäivämäärä
- diaarinumero
- asia / syyte
- vastaaja / vastaajat

Pyydän toimittamaan tiedot sähköisessä muodossa, ensisijaisesti rakenteisessa muodossa, esimerkiksi Excel- tai CSV-tiedostona, tai muutoin sähköpostitse.

Tietojen käyttötarkoitus on rikosasioiden käsittelytietojen journalistinen ja toimituksellinen seuranta sekä mahdollisten jatkotietopyyntöjen kohdentaminen yksittäisiin asioihin. Tietoja ei ole tarkoitus luovuttaa edelleen sellaisenaan kolmansille osapuolille. Mahdollinen myöhempi julkaiseminen tai muu toimituksellinen käyttö arvioidaan erikseen sovellettavan lainsäädännön perusteella.

Tietoja säilytetään sähköisessä muodossa asianmukaisesti suojattuna, ja pääsy niihin on rajattu vain niiden käsittelyn kannalta tarpeellisille henkilöille. Mikäli kaikkia pyydettyjä tietoja ei voida luovuttaa, pyydän toimittamaan ne tiedot, jotka ovat julkisia ja luovutettavissa. Pyydän tällöin myös ilmoittamaan, miltä osin tietoja ei anneta sekä mihin lainkohtaan tai muuhun oikeudelliseen perusteeseen tiedon epääminen perustuu.

Pyydän ensisijaisesti toimittamaan vain sellaiset tiedot, jotka ovat jo valmiiksi sähköisessä muodossa. En pyydä laatimaan uutta asiakirjaa tai muuttamaan paperimuotoista aineistoa sähköiseen muotoon tämän pyynnön johdosta. Mikäli pyyntöä on tarpeen täsmentää, pyydän olemaan yhteydessä sähköpostitse.

Ystävällisin terveisin
{SENDER_NAME}
{SENDER_EMAIL}
{SENDER_PHONE}
"""
    return {
        "recipient_name": court_name,
        "recipient_email": court_email,
        "subject": subject,
        "body": body,
        "status": "draft",
    }


def _has_secure_link(message: InquiryMessage) -> bool:
    return bool((message.secure_link_url or "").strip())


def _is_processed(message: InquiryMessage) -> bool:
    return bool(message.processed_at)


def _message_sort_key(message: InquiryMessage) -> tuple[str, int]:
    return (message.received_at or "", message.id or 0)


def build_inquiry_ingest_preview(inquiry: Inquiry) -> dict:
    messages = sorted(
        list(inquiry.messages or []),
        key=_message_sort_key,
        reverse=True,
    )

    secure_link_messages = [message for message in messages if _has_secure_link(message)]
    response_messages = [
        message for message in messages if message.message_type == "response"
    ]
    processed_messages = [message for message in messages if _is_processed(message)]
    unprocessed_messages = [
        message for message in messages if not _is_processed(message)
    ]

    latest_secure_link_url = (
        secure_link_messages[0].secure_link_url if secure_link_messages else None
    )

    preview_messages = []
    for message in messages:
        preview_messages.append(
            {
                "id": message.id,
                "inquiry_id": message.inquiry_id,
                "message_type": message.message_type,
                "sender": message.sender,
                "subject": message.subject,
                "received_at": message.received_at,
                "raw_sender": message.raw_sender,
                "raw_subject": message.raw_subject,
                "source_email_message_id": message.source_email_message_id,
                "secure_link_url": message.secure_link_url,
                "has_secure_link": _has_secure_link(message),
                "processing_status": message.processing_status,
                "processed_at": message.processed_at,
                "fetch_attempt_count": message.fetch_attempt_count,
                "is_processed": _is_processed(message),
                "notes": message.notes,
            }
        )

    return {
        "inquiry_id": inquiry.id,
        "inquiry_status": inquiry.status,
        "total_messages": len(messages),
        "secure_link_messages": len(secure_link_messages),
        "response_messages": len(response_messages),
        "processed_messages": len(processed_messages),
        "unprocessed_messages": len(unprocessed_messages),
        "latest_secure_link_url": latest_secure_link_url,
        "messages": preview_messages,
    }