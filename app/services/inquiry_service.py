from app.config import SENDER_EMAIL, SENDER_NAME, SENDER_PHONE
from app.models import Court


def build_court_inquiry(court: Court, start_date: str, end_date: str) -> dict:
    court_name = court.name if court else "Käräjäoikeus"
    court_email = court.email if court else None

    subject = f"{court_name} - rikosasioiden käsittelytiedot {start_date}–{end_date}"

    body = f"""Hyvä vastaanottaja,

Tämä on viranomaisten toiminnan julkisuudesta annetun lain (621/1999) 13 §:ään ja 16 §:ään sekä oikeudenkäynnin julkisuudesta yleisissä tuomioistuimissa annetun lain (370/2007) 4 §:ään perustuva tietopyyntö.

Pyydän saada tiedot ajalla {start_date}–{end_date} käsitellyistä tai käsiteltäväksi merkityistä rikosasioista {court_name}.

Pyydän seuraavat julkiset tiedot:
- käsittelypäivämäärä
- diaarinumero
- asia / syyte
- vastaaja / vastaajat

Pyydän toimittamaan tiedot sähköisessä muodossa, ensisijaisesti rakenteisessa muodossa, esimerkiksi Excel- tai CSV-tiedostona, tai muutoin sähköpostitse.

Tietojen käyttötarkoitus on rikosasioiden käsittelytietojen journalistinen ja toimituksellinen seuranta sekä mahdollisten jatkotietopyyntöjen kohdentaminen yksittäisiin asioihin.

Tietoja ei ole tarkoitus luovuttaa edelleen sellaisenaan kolmansille osapuolille. Mahdollinen myöhempi julkaiseminen tai muu toimituksellinen käyttö arvioidaan erikseen sovellettavan lainsäädännön perusteella.

Tietoja säilytetään sähköisessä muodossa asianmukaisesti suojattuna, ja pääsy niihin on rajattu vain niiden käsittelyn kannalta tarpeellisille henkilöille.

Mikäli kaikkia pyydettyjä tietoja ei voida luovuttaa, pyydän toimittamaan ne tiedot, jotka ovat julkisia ja luovutettavissa. Pyydän tällöin myös ilmoittamaan, miltä osin tietoja ei anneta sekä mihin lainkohtaan tai muuhun oikeudelliseen perusteeseen tiedon epääminen perustuu.

Pyydän ensisijaisesti toimittamaan vain sellaiset tiedot, jotka ovat jo valmiiksi sähköisessä muodossa. En pyydä laatimaan uutta asiakirjaa tai muuttamaan paperimuotoista aineistoa sähköiseen muotoon tämän pyynnön johdosta.

Mikäli pyyntöä on tarpeen täsmentää, pyydän olemaan yhteydessä sähköpostitse.

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