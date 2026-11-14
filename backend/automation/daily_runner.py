import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from sqlalchemy import func, select

from database import SessionLocal
from models import Club, ProfileSnapshot, Video, VideoSnapshot

from collectors.tiktok_followers import wykonaj_pomiar
from collectors.tiktok_videos import zapisz_film


# Katalog backend/
BACKEND_DIR = Path(__file__).resolve().parents[1]

# Katalog backend/logs/
LOGS_DIR = BACKEND_DIR / "logs"

logger = logging.getLogger("fsi.automation")


def setup_logging():
    """
    Logowanie do terminala i do pliku.
    Rotacja zapobiega nieograniczonemu rozrastaniu się logów.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOGS_DIR / "fsi_daily.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False


def get_collection_plan(handle, max_videos):
    """
    Znajduje aktywny klub i jego najnowsze znane filmy.
    Niczego nie zapisuje do bazy.
    """
    with SessionLocal() as db:
        club = db.scalar(
            select(Club).where(
                Club.tiktok_handle == handle,
                Club.is_active.is_(True),
            )
        )

        if club is None:
            raise ValueError(
                f"Nie znaleziono aktywnego klubu @{handle}"
            )

        videos = db.scalars(
            select(Video)
            .where(Video.club_id == club.id)
            .order_by(
                Video.published_at.desc(),
                Video.id.desc(),
            )
            .limit(max_videos)
        ).all()

        video_plan = [
            {
                "id": video.id,
                "tiktok_video_id": video.tiktok_video_id,
                "url": video.url,
            }
            for video in videos
        ]

        return club.id, club.name, video_plan


def count_profile_snapshots(club_id):
    with SessionLocal() as db:
        return db.scalar(
            select(func.count(ProfileSnapshot.id))
            .where(ProfileSnapshot.club_id == club_id)
        ) or 0


def count_video_snapshots(video_id):
    with SessionLocal() as db:
        return db.scalar(
            select(func.count(VideoSnapshot.id))
            .where(VideoSnapshot.video_id == video_id)
        ) or 0


async def collect_followers(handle, club_id):
    """
    Wywołuje działający kolektor Playwright.
    Sprawdza, czy faktycznie pojawił się nowy rekord.
    """
    logger.info("Rozpoczynam pobieranie obserwujących.")

    before = count_profile_snapshots(club_id)

    try:
        await wykonaj_pomiar(handle)
    except Exception:
        logger.exception(
            "Wystąpił błąd podczas pobierania obserwujących."
        )
        return False

    after = count_profile_snapshots(club_id)

    if after > before:
        logger.info(
            "Zapisano nowy pomiar obserwujących. "
            "Liczba rekordów: %s -> %s",
            before,
            after,
        )
        return True

    logger.error(
        "Nie zapisano nowego pomiaru obserwujących."
    )
    return False


def collect_video(video):
    """
    Odświeża jeden film przez istniejący kolektor yt-dlp.
    """
    video_id = video["id"]
    tiktok_id = video["tiktok_video_id"]

    logger.info("Rozpoczynam odczyt filmu %s", tiktok_id)

    before = count_video_snapshots(video_id)

    try:
        zapisz_film(url=video["url"])
    except Exception:
        logger.exception(
            "Nie udało się odświeżyć filmu %s",
            tiktok_id,
        )
        return False

    after = count_video_snapshots(video_id)

    if after > before:
        logger.info(
            "Zapisano pomiar filmu %s. Rekordy: %s -> %s",
            tiktok_id,
            before,
            after,
        )
        return True

    logger.error(
        "Nie znaleziono nowego pomiaru dla filmu %s",
        tiktok_id,
    )
    return False


def main():
    parser = argparse.ArgumentParser(
        description="FSI – automatyczne zbieranie danych TikTok"
    )

    parser.add_argument(
        "--handle",
        required=True,
        help="TikTok handle klubu z bazy MySQL",
    )

    parser.add_argument(
        "--mode",
        choices=["followers", "videos", "both"],
        default="both",
        help="Rodzaj zbieranych danych",
    )

    parser.add_argument(
        "--max-videos",
        type=int,
        default=3,
        help="Maksymalna liczba znanych filmów do odświeżenia",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pokaż plan bez pobierania i zapisywania danych",
    )

    args = parser.parse_args()
    setup_logging()

    if not 1 <= args.max_videos <= 20:
        logger.error(
            "--max-videos musi mieć wartość od 1 do 20."
        )
        return 2

    logger.info("=" * 55)
    logger.info("FOOTBALL SOCIAL INTELLIGENCE – DAILY COLLECTION")
    logger.info("Data UTC: %s", datetime.now(timezone.utc))
    logger.info("Klub: @%s", args.handle)
    logger.info("Tryb: %s", args.mode)
    logger.info("=" * 55)

    try:
        club_id, club_name, videos = get_collection_plan(
            args.handle,
            args.max_videos,
        )
    except Exception:
        logger.exception(
            "Nie udało się przygotować planu. "
            "Sprawdź MySQL i konfigurację bazy."
        )
        return 1

    logger.info("Znaleziony klub: %s", club_name)
    logger.info("Filmy do odświeżenia: %s", len(videos))

    if args.dry_run:
        logger.info("TRYB TESTOWY – bez odczytów TikToka.")

        if args.mode in ("followers", "both"):
            logger.info(
                "PLAN: jeden pomiar obserwujących @%s",
                args.handle,
            )

        if args.mode in ("videos", "both"):
            for video in videos:
                logger.info(
                    "PLAN: film %s, MySQL ID %s",
                    video["tiktok_video_id"],
                    video["id"],
                )

        logger.info("Koniec testu – nie zmieniono danych.")
        return 0

    followers_saved = False
    videos_saved = 0
    failures = 0

    # ETAP A – obserwujący
    if args.mode in ("followers", "both"):
        try:
            followers_saved = asyncio.run(
                collect_followers(args.handle, club_id)
            )
            if not followers_saved:
                failures += 1
        except Exception:
            logger.exception(
                "Nieoczekiwany błąd pomiaru obserwujących."
            )
            failures += 1

    # ETAP B – statystyki znanych filmów
    if args.mode in ("videos", "both"):
        if not videos:
            logger.warning(
                "Brak znanych filmów klubu w MySQL."
            )
            failures += 1

        for index, video in enumerate(videos):
            logger.info(
                "Film %s z %s",
                index + 1,
                len(videos),
            )

            try:
                if collect_video(video):
                    videos_saved += 1
                else:
                    failures += 1
            except Exception:
                logger.exception(
                    "Nieoczekiwany błąd obsługi filmu."
                )
                failures += 1

            # Nie wykonujemy kolejnych odczytów bez przerwy.
            if index < len(videos) - 1:
                time.sleep(2)

    logger.info("=" * 55)
    logger.info("PODSUMOWANIE")
    logger.info("Klub: %s", club_name)
    logger.info(
        "Obserwujący – nowy pomiar: %s",
        "TAK" if followers_saved else "NIE",
    )
    logger.info(
        "Zapisane pomiary filmów: %s",
        videos_saved,
    )
    logger.info("Nieudane zadania: %s", failures)
    logger.info("=" * 55)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
