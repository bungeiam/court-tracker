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

    body = f"""Pyydän jäljennöstä asiassa {subject_id} annetusta tuomiosta sekä tiedon siitä, onko asiassa saatavilla muita julkisia oikeudenkäyntiasiakirjoja.

Asia:
- Tuomioistuin: {court_name}
- Asian laji: {case.case_type or 'Ei tiedossa'}
- Asianimike: {case.title or 'Ei tiedossa'}
- Käsittelypäivä / käsittelypäivät: {hearing_dates}
- Asianosaiset: {format_public_parties(case)}

Pyydän asiakirjat ensisijaisesti sähköisessä muodossa.

Ystävällisin terveisin
[OMA NIMI]
[OMA SÄHKÖPOSTI]
[OMA PUHELIN]
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

    body = f"""Pyydän esitutkintapöytäkirjaa asiassa, joka on käsitelty seuraavin tiedoin:

- Tuomioistuin: {case.court.name if case.court else 'Ei tiedossa'}
- Asian laji: {case.case_type or 'Ei tiedossa'}
- Asianimike: {case.title or 'Ei tiedossa'}
- Käsittelypäivä / käsittelypäivät: {hearing_dates}
- Mahdollinen diaarinumero: {case.external_case_id or 'Ei tiedossa'}
- Asianosaiset: {format_public_parties(case)}

Mikäli asia voidaan yksilöidä näillä tiedoilla, pyydän asiakirjat sähköisessä muodossa tai tiedon niiden saatavuudesta.

Ystävällisin terveisin
Joona Teva
joona.teva@gmail.com
+358443278403
"""

    return {
        "request_type": "police_pretrial",
        "recipient_name": "Poliisilaitos / kirjaamo",
        "recipient_email": None,
        "subject": subject,
        "body": body,
        "status": "draft",
    }