from app.database import SessionLocal
from app.models import Court


COURTS = [
    {
        "name": "Ahvenanmaan käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Maarianhamina",
        "email": "aland.tr@om.fi",
        "notes": None,
    },
    {
        "name": "Etelä-Karjalan käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Lappeenranta",
        "email": "etela-karjala.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Etelä-Pohjanmaan käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Seinäjoki",
        "email": "etela-pohjanmaa.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Etelä-Savon käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Mikkeli",
        "email": "etela-savo.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Helsingin käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Helsinki",
        "email": "helsinki.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Itä-Uudenmaan käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Porvoo",
        "email": "ita-uusimaa.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Kainuun käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Kajaani",
        "email": "kainuu.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Kanta-Hämeen käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Hämeenlinna",
        "email": "kanta-hame.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Keski-Suomen käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Jyväskylä",
        "email": "keski-suomi.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Kymenlaakson käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Kouvola",
        "email": "kymenlaakso.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Lapin käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Rovaniemi",
        "email": "lappi.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Länsi-Uudenmaan käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Espoo",
        "email": "lansi-uusimaa.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Oulun käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Oulu",
        "email": "oulu.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Pirkanmaan käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Tampere",
        "email": "pirkanmaa.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Pohjanmaan käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Vaasa",
        "email": "pohjanmaa.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Pohjois-Karjalan käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Joensuu",
        "email": "pohjois-karjala.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Pohjois-Savon käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Kuopio",
        "email": "pohjois-savo.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Päijät-Hämeen käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Lahti",
        "email": "paijat-hame.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Satakunnan käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Pori",
        "email": "satakunta.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Varsinais-Suomen käräjäoikeus",
        "court_level": "käräjäoikeus",
        "city": "Turku",
        "email": "varsinais-suomi.ko@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Helsingin hovioikeus",
        "court_level": "hovioikeus",
        "city": "Helsinki",
        "email": "helsinki.ho@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Itä-Suomen hovioikeus",
        "court_level": "hovioikeus",
        "city": "Kuopio",
        "email": "ita-suomi.ho@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Rovaniemen hovioikeus",
        "court_level": "hovioikeus",
        "city": "Rovaniemi",
        "email": "rovaniemi.ho@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Turun hovioikeus",
        "court_level": "hovioikeus",
        "city": "Turku",
        "email": "turku.ho@oikeus.fi",
        "notes": None,
    },
    {
        "name": "Vaasan hovioikeus",
        "court_level": "hovioikeus",
        "city": "Vaasa",
        "email": "vaasa.ho@oikeus.fi",
        "notes": None,
    },
]


def seed_courts() -> None:
    db = SessionLocal()
    try:
        created_count = 0
        updated_count = 0

        for item in COURTS:
            existing = db.query(Court).filter(Court.name == item["name"]).first()

            if existing:
                existing.court_level = item["court_level"]
                existing.city = item["city"]
                existing.email = item["email"]
                existing.notes = item["notes"]
                updated_count += 1
            else:
                db.add(Court(**item))
                created_count += 1

        db.commit()
        print(
            f"Court seed valmis. Luotiin {created_count}, päivitettiin {updated_count}, yhteensä {len(COURTS)}."
        )
    finally:
        db.close()


def main() -> None:
    seed_courts()


if __name__ == "__main__":
    main()