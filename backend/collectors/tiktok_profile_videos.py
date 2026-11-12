
import argparse
import time
from datetime import datetime

import yt_dlp
from sqlalchemy import select

from database import SessionLocal
from models import Club
from collectors.tiktok_videos import (
    zapisz_film,
    VideoOutsideDateRange,
)


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def pobierz_liste_filmow(handle, cookies_path=None):
    options = {
        "quiet": True,
        "no_warnings": False,
        "extract_flat": True,
        "skip_download": True,
        "noplaylist": False,
    }

    if cookies_path:
        options["cookiefile"] = cookies_path

    url = f"https://www.tiktok.com/@{handle}"

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info or "entries" not in info:
        raise RuntimeError(
            "Nie udało się pobrać listy filmów"
        )

    return list(info["entries"])


def pobierz_filmy_profilu(
    handle,
    start_date,
    end_date,
    cookies_path=None,
    max_videos=10,
    max_scanned=25,
):
    start = parse_date(start_date)
    end = parse_date(end_date)

    if start > end:
        raise ValueError(
            "Data początkowa jest późniejsza niż końcowa"
        )

    if max_videos < 1 or max_scanned < 1:
        raise ValueError(
            "Limity muszą być większe od zera"
        )

    with SessionLocal() as db:
        club = db.scalar(
            select(Club).where(
                Club.tiktok_handle == handle,
                Club.is_active.is_(True)
            )
        )

        if club is None:
            raise ValueError(
                f"Nie znaleziono aktywnego klubu @{handle}"
            )

        club_name = club.name

    print("=" * 55)
    print("FSI – PROFILE VIDEO COLLECTOR")
    print(f"Klub: {club_name} (@{handle})")
    print(f"Okres: {start_date} – {end_date}")
    print(f"Cel: {max_videos} zapisanych pomiarów")
    print(f"Limit sprawdzania: {max_scanned} filmów")
    print("=" * 55)

    entries = pobierz_liste_filmow(
        handle,
        cookies_path
    )

    print(f"\nZnaleziono filmów na profilu: {len(entries)}")

    checked = 0
    saved = 0
    skipped_outside = 0
    skipped_missing = 0
    errors = 0

    for entry in entries:
        # Zatrzymujemy się dopiero po zapisaniu
        # wymaganej liczby pomiarów.
        if saved >= max_videos:
            break

        # Dodatkowy limit bezpieczeństwa:
        # maksymalna liczba szczegółowych odczytów.
        if checked >= max_scanned:
            print("\nOsiągnięto limit sprawdzonych filmów.")
            break

        if not entry:
            skipped_missing += 1
            continue

        video_id = entry.get("id")

        if not video_id:
            skipped_missing += 1
            continue

        video_id = str(video_id)

        url = (
            f"https://www.tiktok.com/"
            f"@{handle}/video/{video_id}"
        )

        checked += 1

        print(
            f"\n[{checked}/{max_scanned}] "
            f"Film {video_id}"
        )

        try:
            # To właśnie tutaj sprawdzamy dokładną
            # datę publikacji przed zapisem do MySQL.
            zapisz_film(
                url=url,
                cookies_path=cookies_path,
                start_date=start_date,
                end_date=end_date,
            )

            saved += 1

            print(
                f"ZAPISANO: {saved}/{max_videos}"
            )

        except VideoOutsideDateRange as error:
            skipped_outside += 1

            print(
                f"POMINIĘTO: {error}"
            )

        except Exception as error:
            errors += 1

            print(
                f"BŁĄD POBIERANIA: {error}"
            )

        # Krótka przerwa pomiędzy próbami.
        if saved < max_videos:
            time.sleep(2)

    print("\n" + "=" * 55)
    print("PODSUMOWANIE FSI")
    print(f"Klub: {club_name}")
    print(f"Okres: {start_date} – {end_date}")
    print(f"Sprawdzone filmy: {checked}")
    print(f"Zapisane pomiary: {saved}")
    print(f"Poza okresem: {skipped_outside}")
    print(f"Brak ID / puste wpisy: {skipped_missing}")
    print(f"Błędy: {errors}")

    if saved < max_videos:
        print(
            "\nNie osiągnięto docelowej liczby "
            "pomiarów w tym uruchomieniu."
        )

    print("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FSI – filmy TikTok z zakresu dat"
    )

    parser.add_argument("--handle", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)

    parser.add_argument(
        "--cookies",
        default=None
    )

    parser.add_argument(
        "--max-videos",
        type=int,
        default=10,
        help="Maksymalna liczba zapisanych pomiarów"
    )

    parser.add_argument(
        "--max-scanned",
        type=int,
        default=25,
        help="Maksymalna liczba sprawdzanych filmów"
    )

    args = parser.parse_args()

    pobierz_filmy_profilu(
        handle=args.handle,
        start_date=args.start,
        end_date=args.end,
        cookies_path=args.cookies,
        max_videos=args.max_videos,
        max_scanned=args.max_scanned,
    )
