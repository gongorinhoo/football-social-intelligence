
import argparse
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import yt_dlp
from sqlalchemy import select

from database import SessionLocal
from models import Club, Video, VideoSnapshot


def parse_video_url(url: str):
    """Weryfikacja adresu filmu TikTok."""
    parsed = urlparse(url)

    if (
        parsed.scheme != "https"
        or parsed.hostname not in ("www.tiktok.com", "tiktok.com")
    ):
        raise ValueError("Adres musi prowadzić do tiktok.com")

    match = re.fullmatch(
        r"/@([\w.-]+)/video/(\d+)/?",
        parsed.path
    )

    if not match:
        raise ValueError("Podaj pełny adres filmu TikTok")

    return match.group(1), match.group(2)


def pobierz_film(url: str, cookies_path=None):
    """Pobranie metadanych bez pobierania pliku wideo."""

    options = {
        "quiet": True,
        "no_warnings": False,
        "skip_download": True,
        "noplaylist": True,
    }

    if cookies_path:
        if not os.path.isfile(cookies_path):
            raise FileNotFoundError(
                "Nie znaleziono pliku cookies"
            )
        options["cookiefile"] = cookies_path

    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=False)


def zapisz_film(
    url: str,
    cookies_path=None,
    start_date=None,
    end_date=None
):
    handle, expected_id = parse_video_url(url)

    # Szukamy klubu w bazie
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

        club_id = club.id
        club_name = club.name

    print(f"Analiza: {club_name}")
    print(f"URL: {url}")

    # Pobieranie danych z TikToka
    info = pobierz_film(url, cookies_path)

    if not info:
        raise RuntimeError("Brak danych filmu")

    video_id = str(info.get("id", ""))

    if video_id != expected_id:
        raise ValueError(
            "ID pobranego filmu nie zgadza się z URL"
        )

    uploader = info.get("uploader")
    if uploader and uploader.lower().lstrip("@") != handle.lower():
        raise ValueError(
            "Autor pobranego filmu nie zgadza się z profilem"
        )

    # Używamy timestamp, jeśli jest dostępny
    timestamp = info.get("timestamp")

    published_at = None

    if timestamp is not None:
        published_at = datetime.fromtimestamp(
            timestamp,
            timezone.utc
        ).replace(tzinfo=None)

    elif info.get("upload_date"):
        published_at = datetime.strptime(
            str(info["upload_date"]),
            "%Y%m%d"
        )

    # Dokładna kontrola zakresu publikacji
    if start_date is not None or end_date is not None:

        if published_at is None:
            raise ValueError(
                "Brak daty publikacji – pomijam film"
            )

        video_date = published_at.date()

        if start_date is not None:
            start = datetime.strptime(
                start_date, "%Y-%m-%d"
            ).date()

            if video_date < start:
                raise ValueError(
                    "Film opublikowany przed wybranym okresem"
                )

        if end_date is not None:
            end = datetime.strptime(
                end_date, "%Y-%m-%d"
            ).date()

            if video_date > end:
                raise ValueError(
                    "Film opublikowany po wybranym okresie"
                )

    metrics = {
        "views_count": info.get("view_count"),
        "likes_count": info.get("like_count"),
        "comments_count": info.get("comment_count"),
        "shares_count": info.get("repost_count"),
    }

    # Nie zapisujemy pustego pomiaru
    if all(value is None for value in metrics.values()):
        raise RuntimeError(
            "Nie udało się pobrać żadnej statystyki filmu"
        )

    for field, value in metrics.items():
        if value is not None and (
            not isinstance(value, int) or value < 0
        ):
            raise ValueError(
                f"Nieprawidłowa statystyka: {field}"
            )

    collected_at = datetime.now(
        timezone.utc
    ).replace(tzinfo=None)

    with SessionLocal.begin() as db:
        video = db.scalar(
            select(Video).where(
                Video.tiktok_video_id == video_id
            )
        )

        if video is None:
            video = Video(
                club_id=club_id,
                tiktok_video_id=video_id,
                url=f"https://www.tiktok.com/@{handle}/video/{video_id}",
                description=info.get("description"),
                published_at=published_at,
            )

            db.add(video)
            db.flush()

        else:
            if video.club_id != club_id:
                raise ValueError(
                    "Film jest przypisany do innego klubu"
                )

            if not video.description:
                video.description = info.get("description")

            if video.published_at is None:
                video.published_at = published_at

        snapshot = VideoSnapshot(
            video_id=video.id,
            collected_at=collected_at,
            **metrics
        )

        db.add(snapshot)
        db.flush()
        internal_id = video.id

    print("\nPOMIAR ZAPISANY")
    print(f"Klub: {club_name}")
    print(f"ID filmu: {video_id}")
    print(f"ID w bazie: {internal_id}")

    for name, value in metrics.items():
        print(f"{name}: {value}")

    print(f"Data odczytu UTC: {collected_at}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--url",
        required=True,
        help="Pełny adres filmu TikTok"
    )

    parser.add_argument(
        "--cookies",
        default=None,
        help="Opcjonalna ścieżka do autoryzowanego pliku cookies"
    )

    args = parser.parse_args()

    try:
        zapisz_film(args.url, args.cookies)
    except Exception as error:
        print(f"BŁĄD: {error}")
        raise SystemExit(1)
