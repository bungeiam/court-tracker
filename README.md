# Court Tracker

Court Tracker on FastAPI-pohjainen MVP-työkalu tuomioistuimille lähetettävien tietopyyntöjen, niihin liittyvien vastausten, muodostettujen casejen, jatkopyyntöjen ja vastaanotettujen dokumenttien operatiiviseen seurantaan.

Projektin tämänhetkinen painopiste on käytännöllisessä inquiry -> response -> case -> request -> document -ketjussa sekä kevyessä selainkäyttöliittymässä, jolla työnkulun eri vaiheita voi hallita ilman erillistä frontend-sovellusta.

## Nykyinen toiminnallisuus

### 1. Court-hallinta
- oikeuksien luonti API:n kautta
- oikeuksien listaus API:n kautta
- court-tietueella kentät:
  - `name`
  - `court_level`
  - `city`
  - `email`
  - `notes`

### 2. Inquiry batchit
- inquiry-batchin luonti
- inquiry-batchien listaus
- yksittäisen batchin haku
- batchin päivitys
- inquiryjen generointi batchille valituille oikeuksille
- duplikaattisuojat:
  - samaan batchiin ei generoida samaa oikeutta toistamiseen

Batchin perusstatusvirta on tällä hetkellä:
- `draft`
- `generated`
- `in_progress`
- `sent`
- `completed`

### 3. Inquiryt
- inquiryjen listaus
- yksittäisen inquiry-rivin haku
- inquiry-rivin päivitys
- inquiry-rivin hyväksyntä
- inquiry-rivin lähetys SMTP:n kautta
- kaikkien hyväksyttyjen inquiryjen massalähetys

Inquiry-rivi sisältää mm.:
- vastaanottajan nimen ja sähköpostin
- subjectin ja bodyn
- statuksen
- `sent_at`
- `acknowledged_at`
- `responded_at`
- omat muistiinpanot

### 4. Inquiry-viestit
Järjestelmässä inquiryyn voidaan tallentaa siihen liittyviä viestejä, esimerkiksi:
- kuittausviesti
- varsinainen vastausviesti

Tuettu toiminnallisuus:
- viestin luonti inquiryyn
- inquiryyn liittyvien viestien listaus
- yksittäisen inquiry-viestin haku

Inquiry-viestillä voidaan tallentaa mm.:
- `message_type`
- `sender`
- `subject`
- `body`
- `received_at`
- `file_path`
- `mime_type`
- `notes`

### 5. Vastausviestien parseri ja case-luonti
Inquiry-vastauksen `body` voidaan parsia rakenteiseksi case-dataksi.

Nykyinen parseri osaa:
- lukea vastausrivejä inquiry-vastauksesta
- tunnistaa diaarinumeron / external case id:n
- tunnistaa otsikkoa / asiaa
- tunnistaa päivämäärää
- tunnistaa käsittelytyyppiä
- palauttaa myös rivit, joita ei pystytty jäsentämään

Case-luonti inquiry-vastauksesta sisältää tällä hetkellä:
- casejen muodostamisen response-viestistä
- hearing date -rivien luonnin
- kiinnostavuusarvion tallennuksen (`interest_score`, `interest_notes`)
- duplikaattitarkistuksen saman courtin + external case id:n + otsikon perusteella

### 6. Caset
- casejen listaus
- yksittäisen casen haku
- follow-up-valittujen casejen seurantanäkymä:
  - `/cases/tracking/missing-requests`
- case selection -päivitys:
  - follow-up-valinta
  - kiinnostavuuspisteet
  - kiinnostavuusmuistiinpanot
- hearing date -rivien lisäys
- party-rivien lisäys

Case-mallissa on mm.:
- `external_case_id`
- `case_type`
- `title`
- `summary`
- `public_status`
- `source_method`
- `source_reference`
- `raw_text`
- `interest_score`
- `interest_notes`
- `selected_for_followup`
- `status`

### 7. Requestit
Caseista voidaan luoda jatkopyyntöjä.

Nykyinen toiminnallisuus:
- requestien listaus
- open/replied/missing-documents -seurantanäkymät
- yksittäisen requestin haku
- requestin päivitys
- requestin hyväksyntä
- requestin lähetys SMTP:n kautta
- kaikkien hyväksyttyjen requestien massalähetys
- requestin merkitseminen replied-tilaan
- court-requestin generointi casesta
- police-requestin generointi casesta

Request-rivi sisältää mm.:
- `request_type`
- `recipient_name`
- `recipient_email`
- `subject`
- `body`
- `status`
- `sent_at`
- `response_due_date`
- `response_summary`

### 8. Dokumentit
Dokumentit voidaan tallentaa joko:
- suoraan caseen
- tai requestiin liittyen

Nykyinen toiminnallisuus:
- dokumentin upload caseen
- dokumentin upload requestiin
- caseen liittyvien dokumenttien listaus
- yksittäisen dokumentin haku
- dokumentin lataus
- dokumentin poisto
- dokumentin metatietojen päivitys

Tallennuslogiikka:
- tiedostot tallennetaan levylle `storage/`-hakemiston alle
- käytössä on case-kohtainen kansiorakenne tyyliin `storage/case_<id>/`

Dokumenttirivillä on mm.:
- `document_type`
- `title`
- `description`
- `source`
- `sender`
- `file_path`
- `mime_type`
- `public_status`
- `received_date`
- `notes`

### 9. Exportit
- selected-for-followup -caset voidaan viedä export-endpointin kautta:
  - `GET /exports/selected-cases`

### 10. Kevyt selain-UI
Projektissa on nyt mukana kevyt Jinja2-templateihin perustuva käyttöliittymä.

UI sisältää tällä hetkellä:
- dashboard
- inquiries-lista
- cases-lista
- requests-lista
- inquiry batch detail
- inquiry detail
- case detail
- request detail
- document detail

UI:n kautta voi tehdä keskeisiä operatiivisia toimintoja, kuten:
- lähettää inquiryjä
- luoda caseja inquiry-vastauksesta
- hyväksyä ja lähettää requestejä
- uploadata dokumentteja caseen
- tarkastella työjonoja ja statuksia

## Nykyinen työnkulku

Tämänhetkinen päävirta on:

1. luo oikeudet (`courts`)
2. luo inquiry-batch
3. generoi inquiryt valituille oikeuksille
4. tarkista ja hyväksy inquiryt
5. lähetä inquiryt
6. tallenna inquiryyn saapuneet viestit
7. muodosta response-viestistä caset
8. valitse kiinnostavat caset follow-upiin
9. generoi requestit caseista
10. hyväksy ja lähetä requestit
11. tallenna saapuneet dokumentit caseihin / requesteihin
12. seuraa puuttuvia requesteja ja puuttuvia dokumentteja UI:ssa

## Mitä projektissa ei vielä ole

Seuraavia asioita ei ole vielä integroitu varsinaiseen court-trackeriin:

- secure mail -hakulogiiikka
- secure linkkien automaattinen käsittely
- secure mail job -mallinnus
- ZIP-pakettien automaattinen purku osaksi documents-ketjua
- varsinainen taustatyö- / scheduler-ajastus kuukausiajoille
- court-seedauksen valmis tuotantoversio repo-tasolla
- migraatiopohjainen tietokantamuutosten hallinta

## Tekninen rakenne

Nykyinen repo on rakenteeltaan kevyt ja tarkoituksella MVP-henkinen.

### Hakemistot
- `app/`
  - FastAPI-sovellus
  - route-moduulit
  - palvelut
  - tietokantamalli
  - skeemat
- `templates/`
  - Jinja2 HTML-templateit
- `static/`
  - käyttöliittymän CSS
- `scripts/`
  - apuskriptit, tällä hetkellä ainakin tietokannan alustus
- `tests/`
  - pytest-testit
- `storage/`
  - ladattujen dokumenttien tallennus levylle ajon aikana

### Tärkeimmät tiedostot
- `app/main.py`
- `app/models.py`
- `app/database.py`
- `app/config.py`
- `app/routes/`
- `app/services/`
- `scripts/init_db.py`

## Tietokanta

Nykyinen tietokanta on SQLite:

- tiedostopolku: `sqlite:///./court_tracker.db`

Tietokanta alustetaan suoraan SQLAlchemy-malleista ilman erillisiä migraatioita.

## Konfiguraatio

Sovellus lukee sähköpostilähetyksen asetuksia ympäristömuuttujista.

Nykyiset käytössä olevat muuttujat:

```env
COURT_TRACKER_SENDER_NAME=
COURT_TRACKER_SENDER_EMAIL=
COURT_TRACKER_SENDER_PHONE=

SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_FROM_NAME=Court Tracker
SMTP_USE_TLS=true