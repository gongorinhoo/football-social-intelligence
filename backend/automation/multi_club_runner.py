
import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from logging.handlers import RotatingFileHandler

from sqlalchemy import func, select

from database import SessionLocal
from models import Club, Video


BACKEND_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = BACKEND_DIR / "logs"

logger = logging.getLogger("fsi.multi_club")


def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOGS_DIR / "fsi_multi.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    logger.setLevel(logging.INFO)

    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()

    logger.addHandler(console)
    logger.addHandler(file_handler)
    logger.propagate = False


def parse_handles(value):
    """
    Zamienia np.:
    sandecjans,wislakrakowsa

    na listę unikalnych nazw profili.
    """
    if not value:
        return None

    handles = [
        item.strip().lstrip("@").lower()
        for item in value.split(",")
        if item.strip()
    ]

    return list(dict.fromkeys(handles)) or None


def get_clubs(handles, max_clubs):
    """
    Pobiera aktywne kluby z MySQL wraz z liczbą
    zapisanych filmów. Nie modyfikuje bazy.
    """
    with SessionLocal() as db:
        query = (
            select(
                Club.name,
                Club.tiktok_handle,
                func.count(Video.id).label("video_count"),
            )
            .select_from(Club)
            .outerjoin(
                Video,
                Video.club_id == Club.id,
            )
            .where(Club.is_active.is_(True))
            .group_by(
                Club.id,
                Club.name,
                Club.tiktok_handle,
            )
            .order_by(Club.name.asc())
        )

        if handles:
            query = query.where(
                Club.tiktok_handle.in_(handles)
            )

        rows = db.execute(query).all()

    if handles:
        found = {
            str(handle).lower()
            for _, handle, _ in rows
        }

        missing = [
            handle
            for handle in handles
            if handle not in found
        ]

        if missing:
            raise ValueError(
                "Nie znaleziono aktywnych klubów: "
                + ", ".join(missing)
            )

    clubs = []

    for name, handle, video_count in rows[:max_clubs]:
        clubs.append({
            "name": name,
            "handle": handle,
            "video_count": int(video_count),
        })

    return clubs, len(rows)


def get_effective_mode(requested_mode, video_count):
    """
    Klub bez zapisanych filmów:
    - both -> pobieramy tylko obserwujących
    - videos -> pomijamy klub
    """
    if video_count == 0:
        if requested_mode == "both":
            return "followers"

        if requested_mode == "videos":
            return None

    return requested_mode


def run_club(club, mode, max_videos, timeout_seconds):
    """
    Uruchamia istniejący daily_runner jako
    osobny proces Python.

    Każdy klub jest wykonywany kolejno.
    """
    command = [
        sys.executable,
        "-m",
        "automation.daily_runner",
        "--handle",
        club["handle"],
        "--mode",
        mode,
        "--max-videos",
        str(max_videos),
    ]

    logger.info(
        "START: %s (@%s), tryb=%s, limit filmów=%s",
        club["name"],
        club["handle"],
        mode,
        max_videos,
    )

    # Zachowujemy istniejące zmienne środowiskowe,
    # w tym konfigurację połączenia z bazą.
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"

    try:
        result = subprocess.run(
            command,
            cwd=str(BACKEND_DIR),
            env=environment,
            timeout=timeout_seconds,
            check=False,
        )

        if result.returncode == 0:
            logger.info(
                "SUKCES: %s",
                club["name"],
            )
            return True

        logger.error(
            "BŁĄD: %s, kod zakończenia=%s",
            club["name"],
            result.returncode,
        )
        return False

    except subprocess.TimeoutExpired:
        logger.error(
            "PRZEKROCZONO CZAS: %s (%s sekund)",
            club["name"],
            timeout_seconds,
        )
        return False

    except Exception:
        logger.exception(
            "Nie udało się uruchomić zadania: %s",
            club["name"],
        )
        return False


def main():
    parser = argparse.ArgumentParser(
        description="FSI – automatyzacja wielu klubów"
    )

    parser.add_argument(
        "--handles",
        default=None,
        help="Lista profili oddzielonych przecinkami",
    )

    parser.add_argument(
        "--mode",
        choices=["followers", "videos", "both"],
        default="both",
    )

    parser.add_argument(
        "--max-clubs",
        type=int,
        default=3,
        help="Maksymalna liczba klubów w jednym cyklu",
    )

    parser.add_argument(
        "--max-videos",
        type=int,
        default=3,
        help="Maksymalna liczba filmów na klub",
    )

    parser.add_argument(
        "--pause-seconds",
        type=int,
        default=30,
        help="Przerwa pomiędzy klubami",
    )

    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=900,
        help="Limit czasu pracy jednego klubu",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pokaż plan bez pobierania TikToka",
    )

    args = parser.parse_args()
    setup_logging()

    if not 1 <= args.max_clubs <= 100:
        parser.error("--max-clubs musi być od 1 do 100")

    if not 1 <= args.max_videos <= 20:
        parser.error("--max-videos musi być od 1 do 20")

    if not 5 <= args.pause_seconds <= 300:
        parser.error(
            "--pause-seconds musi być od 5 do 300"
        )

    if not 60 <= args.timeout_seconds <= 3600:
        parser.error(
            "--timeout-seconds musi być od 60 do 3600"
        )

    handles = parse_handles(args.handles)

    logger.info("=" * 60)
    logger.info("FSI – MULTI-CLUB SCHEDULER")
    logger.info("Tryb: %s", args.mode)
    logger.info("Limit klubów: %s", args.max_clubs)
    logger.info("Limit filmów na klub: %s", args.max_videos)
    logger.info(
        "Przerwa między klubami: %s s",
        args.pause_seconds,
    )
    logger.info("=" * 60)

    try:
        clubs, available_count = get_clubs(
            handles,
            args.max_clubs,
        )
    except Exception:
        logger.exception(
            "Nie udało się pobrać listy klubów z MySQL."
        )
        return 1

    if not clubs:
        logger.warning("Brak klubów do przetworzenia.")
        return 0

    logger.info(
        "Aktywne kluby pasujące do wyboru: %s",
        available_count,
    )
    logger.info(
        "Kluby w bieżącym cyklu: %s",
        len(clubs),
    )

    # Najpierw pokazujemy pełny plan.
    jobs = []

    for club in clubs:
        effective_mode = get_effective_mode(
            args.mode,
            club["video_count"],
        )

        jobs.append((club, effective_mode))

        if effective_mode is None:
            logger.info(
                "PLAN: %s – brak znanych filmów, "
                "zadanie videos zostanie pominięte",
                club["name"],
            )
        else:
            logger.info(
                "PLAN: %s (@%s) – tryb=%s, "
                "znane filmy=%s",
                club["name"],
                club["handle"],
                effective_mode,
                club["video_count"],
            )

    if args.dry_run:
        logger.info(
            "DRY RUN – nie pobierano TikToka "
            "i nie zapisano żadnych pomiarów."
        )
        return 0

    succeeded = 0
    failed = 0
    skipped = 0

    executable_jobs = [
        job for job in jobs if job[1] is not None
    ]

    for index, (club, effective_mode) in enumerate(jobs):
        if effective_mode is None:
            skipped += 1
            continue

        success = run_club(
            club=club,
            mode=effective_mode,
            max_videos=args.max_videos,
            timeout_seconds=args.timeout_seconds,
        )

        if success:
            succeeded += 1
        else:
            failed += 1

        # Przerwa po klubie, jeśli czeka jeszcze kolejny.
        remaining = jobs[index + 1:]

        if any(mode is not None for _, mode in remaining):
            logger.info(
                "Przerwa %s sekund przed kolejnym klubem.",
                args.pause_seconds,
            )
            time.sleep(args.pause_seconds)

    logger.info("=" * 60)
    logger.info("PODSUMOWANIE MULTI-CLUB")
    logger.info("Kluby przetworzone poprawnie: %s", succeeded)
    logger.info("Kluby z błędami: %s", failed)
    logger.info("Kluby pominięte: %s", skipped)
    logger.info("Zadania do wykonania: %s", len(executable_jobs))
    logger.info("=" * 60)

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
