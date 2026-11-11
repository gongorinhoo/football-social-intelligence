
import argparse
import asyncio
import re
from datetime import datetime, timezone

from playwright.async_api import (
    async_playwright,
    TimeoutError as PlaywrightTimeoutError,
)
from sqlalchemy import select

from database import SessionLocal
from models import Club, ProfileSnapshot


def parse_followers(value: str) -> tuple[int, bool]:
    """
    Zamienia tekst z TikToka na liczbę.
    Zwraca: (liczba, czy_wartosc_przyblizona)
    """

    text = (
        value.strip()
        .lower()
        .replace("\u00a0", "")
        .replace("\u202f", "")
        .replace(" ", "")
    )

    match = re.fullmatch(
        r"([\d.,]+)(tys\.?|k|mln\.?|m)?",
        text
    )

    if not match:
        raise ValueError(f"Nieznany format liczby: {value!r}")

    number, suffix = match.groups()

    if suffix:
        multiplier = 1_000 if suffix.startswith(("tys", "k")) else 1_000_000
        result = round(float(number.replace(",", ".")) * multiplier)
        return result, True

    # Bez skrótu traktujemy separatory jako separatory tysięcy
    if not re.fullmatch(
        r"\d+|[1-9]\d{0,2}([.,]\d{3})+",
        number
    ):
        raise ValueError(f"Niejasny format liczby: {value!r}")

    result = int(number.replace(",", "").replace(".", ""))
    return result, False


async def pobierz_obserwujacych(page, handle: str):
    url = f"https://www.tiktok.com/@{handle}"

    await page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=30000
    )

    selector = '[data-e2e="followers-count"]'

    await page.locator(selector).wait_for(
        state="visible",
        timeout=15000
    )

    followers_text = await page.locator(selector).inner_text()

    followers, approximate = parse_followers(followers_text)

    return followers, approximate, followers_text


async def wykonaj_pomiar(handle: str):
    # Pobieramy klub z MySQL
    with SessionLocal() as db:
        club = db.scalar(
            select(Club).where(
                Club.tiktok_handle == handle,
                Club.is_active.is_(True)
            )
        )

        if club is None:
            print(f"Nie znaleziono aktywnego klubu @{handle}")
            return

        club_id = club.id
        club_name = club.name

    print(f"\nFSI – Pomiar: {club_name}")
    print(f"Profil: @{handle}")

    # Jeden odczyt z TikToka
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            try:
                context = await browser.new_context(
                    locale="pl-PL"
                )
                page = await context.new_page()

                followers, approximate, raw_text = (
                    await pobierz_obserwujacych(page, handle)
                )
            finally:
                await browser.close()

    except PlaywrightTimeoutError:
        print("Nie udało się odczytać licznika w wyznaczonym czasie.")
        print("Pomiar NIE został zapisany.")
        return

    except Exception as error:
        print(f"Błąd podczas pobierania: {error}")
        print("Pomiar NIE został zapisany.")
        return

    # Zapis pomiaru w MySQL
    try:
        with SessionLocal.begin() as db:
            snapshot = ProfileSnapshot(
                club_id=club_id,
                followers_count=followers,
                likes_count=None,
                collected_at=datetime.now(timezone.utc).replace(
                    tzinfo=None
                )
            )

            db.add(snapshot)

    except Exception as error:
        print(f"Błąd zapisu do MySQL: {error}")
        return

    print("\nPOMIAR ZAPISANY")
    print(f"Klub: {club_name}")
    print(f"Odczyt z TikToka: {raw_text}")
    print(f"Obserwujący: {followers:,}".replace(",", " "))

    if approximate:
        print("Uwaga: wynik jest przybliżony (TikTok zaokrągla licznik).")

    print("Dane zapisane w tabeli profile_snapshots.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FSI – kolektor obserwujących TikTok"
    )
    parser.add_argument(
        "--handle",
        default="wislakrakowsa",
        help="TikTok handle klubu z bazy danych"
    )

    args = parser.parse_args()

    asyncio.run(wykonaj_pomiar(args.handle))
