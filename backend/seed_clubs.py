
from sqlalchemy import select, func, or_

from database import Base, engine, SessionLocal
from models import Club


KLUBY_DICT = {
    "Wisła Płock": "wislaplocksa",
    "Górnik Zabrze": "gornikzabrzesa",
    "Pogoń Szczecin": "pogonszczecinsa",
    "Widzew Łódź": "rts_widzew_lodz",
    "Jagiellonia Białystok": "jagielloniabialystok1920",
    "Motor Lublin": "motorlublin.official",
    "Arka Gdynia": "arkagdynia_sa",
    "Świt Szczecin": "swit.szczecin",
    "Raków Częstochowa": "rakow.czestochowa",
    "Lech Poznań": "lechpoznan",
    "Legia Warszawa": "legiawarszawa",
    "Cracovia": "kscracovia1906",
    "Sandecja Nowy Sącz": "sandecjans",
    "Znicz Pruszków": "zniczpruszkow.official",
    "Śląsk Wrocław": "slaskwroclawpl",
    "GKS Katowice": "gksgieksakatowice",
    "Zagłębie Lubin": "zaglebielubin",
    "Korona Kielce": "korona.kielce",
    "Polonia Bytom": "bspoloniabytom",
    "Podbeskidzie BB": "ts.podbeskidziebb",
    "Warta Poznań": "warta.poznan",
    "Rekord BB": "rekord_bb",
    "Lechia Gdańsk": "lechiagdansk_official",
    "Piast Gliwice": "piastgliwicesa",
    "GKS Tychy": "kp_gkstychy",
    "ŁKS Łódź": "lkslodz",
    "Radomiak Radom": "1910radomiak_",
    "Podhale Nowy Targ": "nkppodhale",
    "Ruch Chorzów": "ruchchorzow_1920",
    "Resovia Rzeszów": "cwksresoviapl",
    "Górnik Łęczna": "zielono_czarni",
    "Stal Rzeszów": "stal1944",
    "Wisła Kraków": "wislakrakowsa",
    "Pogoń Grodzisk Mazowiecki": "pogongrodziskofficial",
    "Miedź Legnica": "miedz.legnica",
    "Bruk-Bet Termalica": "brukbet.termalica",
    "Avia Świdnik": "mksaviaswidnik",
    "Stal Stalowa Wola": "stal.stalowa.wola.psa",
    "Polonia Warszawa": "poloniawarszawa_official",
    "Chojniczanka Chojnice": "chojniczanka1930",
    "Odra Opole": "odraopole.pl",
    "Unia Skierniewice": "unia_skierniewice",
    "Chrobry Głogów": "chrobryglogowofficial",
    "Stal Mielec": "fksstalmielec",
    "Pogoń Siedlce": "mkspogonsiedlce",
    "Puszcza Niepołomice": "mkspuszczaniepolomice",
    "Hutnik Kraków": "kshutnikkrakow",
    "Sokół Kleczew": "sokolkleczew",
    "Lechia Zielona Góra": "lechiazg",
}


def import_clubs():
    # Upewniamy się, że tabela istnieje
    Base.metadata.create_all(bind=engine)

    inserted = 0
    updated = 0

    with SessionLocal() as db:
        try:
            for name, handle in KLUBY_DICT.items():

                existing = db.scalar(
                    select(Club).where(
                        or_(
                            Club.tiktok_handle == handle,
                            Club.name == name
                        )
                    )
                )

                if existing:
                    existing.name = name
                    existing.tiktok_handle = handle
                    existing.is_active = True
                    updated += 1

                else:
                    club = Club(
                        name=name,
                        tiktok_handle=handle,
                        is_active=True
                    )
                    db.add(club)
                    inserted += 1

            db.commit()

            total = db.scalar(
                select(func.count()).select_from(Club)
            )

            print("=" * 50)
            print("FOOTBALL SOCIAL INTELLIGENCE")
            print("IMPORT KLUBÓW ZAKOŃCZONY")
            print("=" * 50)
            print(f"Liczba klubów w słowniku: {len(KLUBY_DICT)}")
            print(f"Nowo dodane: {inserted}")
            print(f"Zaktualizowane: {updated}")
            print(f"Łącznie w bazie: {total}")
            print("=" * 50)

        except Exception:
            db.rollback()
            raise


if __name__ == "__main__":
    import_clubs()
