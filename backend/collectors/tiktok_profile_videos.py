
import argparse
import time
from datetime import datetime, timedelta, timezone

import yt_dlp
from sqlalchemy import select

from database import SessionLocal
from models import Club
from collectors.tiktok_videos import zapisz_film


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
            "Nie udało się pobrać listy filmów profilu"
        )

    entries = list(info["entries"])
    return entries


def parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def pobierz_filmy_profilu(
    handle,
    start_date,
    end_date,
    cookies_path=None,
    max_videos=20,
):
    start = parse_date(start_date)
    end = parse_date(end_date)

    if start > end:
        raise ValueError(
            "Data początkowa nie może być późniejsza niż końcowa"
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
    print(f"FSI – PROFILE VIDEO COLLECTOR")
    print(f"Klub: {club_name} (@{handle})")
    print(f"Zakres: {start_date} – {end_date}")
    print("=" * 55)

    entries = pobierz_liste_filmow(
        handle, cookies_path
    )

    print(f"Znaleziono pozycji na profilu: {len(entries)}")

    zapisane = 0
    pominiete = 0
    bledy = 0
    sprawdzone = 0

    for entry in entries:
        if sprawdzone >= max_videos:
            break

        if not entry:
            continue

        video_id = entry.get("id")

        if not video_id:
            pominiete += 1
            continue

        # Wstępna data, o ile jest dostępna
        upload_date = entry.get("upload_date")

        if upload_date:
            try:
                published = datetime.strptime(
                    upload_date, "%Y%m%d"
                ).date()

                if not (start <= published <= end):
                    pominiete += 1
                    continue

            except ValueError:
                pass

        url = (
            f"https://www.tiktok.com/@{handle}/video/{video_id}"
        )

        sprawdzone += 1

        print(
            f"\n[{sprawdzone}/{max_videos}] "
            f"Film: {video_id}"
        )

        try:
            zapisz_film(
                url=url,
                cookies_path=cookies_path,
                start_date=start_date,
                end_date=end_date
            )
            zapisane += 1

        except Exception as error:
            print(f"Błąd filmu: {error}")
            bledy += 1

        time.sleep(2)

    print("\n" + "=" * 55)
    print("PODSUMOWANIE")
    print(f"Sprawdzone filmy: {sprawdzone}")
    print(f"Zapisane pomiary: {zapisane}")
    print(f"Pominięte: {pominiete}")
    print(f"Błędy: {bledy}")
    print("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--handle", required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--cookies", default=None)
    parser.add_argument(
        "--max-videos",
        type=int,
        default=20
    )

    args = parser.parse_args()

    pobierz_filmy_profilu(
        handle=args.handle,
        start_date=args.start,
        end_date=args.end,
        cookies_path=args.cookies,
        max_videos=args.max_videos,
    )
