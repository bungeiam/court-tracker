from app.config import SENDER_EMAIL, SENDER_NAME, SENDER_PHONE
from app.models import Case


def format_hearing_dates(case: Case) -> str:
    if not case.hearing_dates:
        return "Ei tiedossa"

    dates = sorted(
        [item.hearing_date for item in case.hearing_dates if item.hearing_date]
    )
    return ", ".join(dates)


def format_public_parties(case: Case) -> str:
    public_names = [p.name for p in case.parties if p.is_public == 1 and p.name]
    if not public_names:
        return "Ei ilmoitettu"
    return ", ".join(public_names)


def build_court_request(case: Case) -> dict:
    court_name = case.court.name if case.court else "Tuomioistuin"
    court_email = case.court.email if case.court else None
    hearing_dates = format_hearing_dates(case)
    subject_id = case.external_case_id or f"case-{case.id}"

    subject = f"Tietopyyntö asiassa {subject_id}"

    body = f"""Hyvä vastaanottaja,

Pyydän jäljennöstä asiassa {subject_id} annetusta tuomiosta sekä tiedon siitä, onko asiassa saatavilla muita julkisia oikeudenkäyntiasiakirjoja.

Asia:
- tuomioistuin: {court_name}
- asian laji: {case.case_type or 'Ei tiedossa'}
- asianimike: {case.title or 'Ei tiedossa'}
- käsittelypäivä / käsittelypäivät: {hearing_dates}
- asianosaiset: {format_public_parties(case)}

Pyydän asiakirjat ensisijaisesti sähköisessä muodossa.

Mikäli kaikkia pyydettyjä asiakirjoja tai tietoja ei voida luovuttaa, pyydän toimittamaan ne asiakirjat ja tiedot, jotka ovat julkisia ja luovutettavissa. Pyydän tällöin myös ilmoittamaan, miltä osin tietoja ei anneta sekä mihin lainkohtaan tai muuhun oikeudelliseen perusteeseen tiedon epääminen perustuu.

Pyydän ensisijaisesti toimittamaan vain sellaiset asiakirjat ja tiedot, jotka ovat jo valmiiksi sähköisessä muodossa. En pyydä laatimaan uutta asiakirjaa tai muuttamaan paperimuotoista aineistoa sähköiseen muotoon tämän pyynnön johdosta.

Ystävällisin terveisin

{SENDER_NAME}
{SENDER_EMAIL}
{SENDER_PHONE}
"""

    return {
        "request_type": "court_documents",
        "recipient_name": court_name,
        "recipient_email": court_email,
        "subject": subject,
        "body": body,
        "status": "draft",
    }


def build_police_request(case: Case) -> dict:
    hearing_dates = format_hearing_dates(case)
    subject = "Asiakirjapyyntö / esitutkintapöytäkirja"

    body = f"""Hyvä vastaanottaja,

Pyydän esitutkintapöytäkirjaa asiassa, joka on käsitelty seuraavin tiedoin:

- tuomioistuin: {case.court.name if case.court else 'Ei tiedossa'}
- asian laji: {case.case_type or 'Ei tiedossa'}
- asianimike: {case.title or 'Ei tiedossa'}
- käsittelypäivä / käsittelypäivät: {hearing_dates}
- mahdollinen diaarinumero: {case.external_case_id or 'Ei tiedossa'}
- asianosaiset: {format_public_parties(case)}

Mikäli asia voidaan yksilöidä näillä tiedoilla, pyydän asiakirjat sähköisessä muodossa tai tiedon niiden saatavuudesta.

Mikäli kaikkia pyydettyjä asiakirjoja tai tietoja ei voida luovuttaa, pyydän toimittamaan ne asiakirjat ja tiedot, jotka ovat julkisia ja luovutettavissa. Pyydän tällöin myös ilmoittamaan, miltä osin tietoja ei anneta sekä mihin lainkohtaan tai muuhun oikeudelliseen perusteeseen tiedon epääminen perustuu.

Pyydän ensisijaisesti toimittamaan vain sellaiset asiakirjat ja tiedot, jotka ovat jo valmiiksi sähköisessä muodossa. En pyydä laatimaan uutta asiakirjaa tai muuttamaan paperimuotoista aineistoa sähköiseen muotoon tämän pyynnön johdosta.

Ystävällisin terveisin

{SENDER_NAME}
{SENDER_EMAIL}
{SENDER_PHONE}
"""

    return {
        "request_type": "police_pretrial",
        "recipient_name": "Poliisilaitos / kirjaamo",
        "recipient_email": None,
        "subject": subject,
        "body": body,
        "status": "draft",
    }