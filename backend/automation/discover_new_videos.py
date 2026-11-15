
import argparse
import logging
import re
import sys
import time

from datetime import datetime, timedelta, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from sqlalchemy import select

from database import SessionLocal
from models import Club, Video

from automation.multi_club_runner import (
    get_clubs,
    parse_handles,
)

from collectors.tiktok_profile_videos import (
    pobierz_liste_filmow,
)

from collectors.tiktok_videos import (
    zapisz_film,
    VideoOutsideDateRange,
)


BACKEND_DIR = Path(__file__).resolve().parents[1]
LOGS_DIR = BACKEND_DIR / "logs"

logger = logging.getLogger("fsi.discovery")


def setup_logging():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOGS_DIR / "fsi_discovery.log",
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


def get_known_video_ids(handle):
    """
    Pobiera identyfikatory filmów, które już są w MySQL.
    Nie zmienia danych.
    """
    with SessionLocal() as db:
        query = (
            select(Video.tiktok_video_id)
            .join(Club, Video.club_id == Club.id)
            .where(Club.tiktok_handle == handle)
        )

        return set(db.scalars(query).all())


def build_candidates(entries, known_ids, max_scanned):
    """
    Analizuje maksymalnie max_scanned pozycji z profilu.

    Zwraca:
    - listę ID filmów nieznanych w MySQL
    - liczbę znanych filmów
    - liczbę pominiętych nieprawidłowych wpisów

    Na tym etapie nie znamy jeszcze pewnej daty publikacji.
    """
    candidates = []
    seen = set()

    known_count = 0
    invalid_count = 0

    for entry in entries[:max_scanned]:

        if not isinstance(entry, dict):
            invalid_count += 1
            continue

        video_id = str(entry.get("id") or "").strip()

        # Typowy identyfikator numeryczny filmu TikTok
        if not re.fullmatch(r"[0-9]{16,22}", video_id):
            invalid_count += 1
            continue

        # Duplikat w pobranej liście
        if video_id in seen:
            continue

        seen.add(video_id)

        # Film istnieje już w bazie
        if video_id in known_ids:
            known_count += 1
            continue

        candidates.append(video_id)

    return candidates, known_count, invalid_count


def discover_for_club(club, args, start_date, end_date):
    """
    Wykrywa filmy klubu, których nie ma w bazie.
    Przed zapisem sprawdza rzeczywistą datę publikacji.
    """
    handle = club["handle"]
    name = club["name"]

    logger.info("-" * 60)
    logger.info("KLUB: %s (@%s)", name, handle)

    # 1. Stan istniejącej bazy danych
    try:
        known_ids = get_known_video_ids(handle)
    except Exception:
        logger.exception(
            "Nie udało się odczytać istniejących filmów."
        )
        return False

    logger.info(
        "Znane filmy w MySQL: %s",
        len(known_ids),
    )

    # 2. Lista filmów dostępna na profilu
    try:
        entries = pobierz_liste_filmow(handle)
    except Exception:
        logger.exception(
            "Nie udało się pobrać listy filmów profilu."
        )
        return False

    logger.info(
        "Pozycje zwrócone przez TikToka: %s",
        len(entries),
    )

    # 3. Porównanie ID z bazą
    candidates, known_count, invalid_count = (
        build_candidates(
            entries,
            known_ids,
            args.max_scanned,
        )
    )

    logger.info(
        "Sprawdzone pozycje listy: %s",
        min(len(entries), args.max_scanned),
    )

    logger.info(
        "Już w bazie: %s",
        known_count,
    )

    logger.info(
        "Nowe kandydatury (niezweryfikowane): %s",
        len(candidates),
    )

    logger.info(
        "Nieprawidłowe wpisy listy: %s",
        invalid_count,
    )

    # 4. Tryb testowy
    if args.dry_run:
        logger.info(
            "DRY RUN – nie pobieram szczegółów "
            "i nie zapisuję filmów."
        )

        for video_id in candidates[:args.max_details]:
            logger.info(
                "KANDYDAT: %s",
                video_id,
            )

        return True

    saved = 0
    attempts = 0
    skipped_date = 0
    missing_date = 0
    errors = 0

    # 5. Weryfikacja kandydatów
    for video_id in candidates:

        if saved >= args.max_new:
            logger.info(
                "Osiągnięto limit nowych filmów."
            )
            break

        if attempts >= args.max_details:
            logger.info(
                "Osiągnięto limit szczegółowych odczytów."
            )
            break

        attempts += 1

        url = (
            f"https://www.tiktok.com/"
            f"@{handle}/video/{video_id}"
        )

        logger.info(
            "ODCZYT %s/%s: %s",
            attempts,
            args.max_details,
            video_id,
        )

        try:
            # Używa dotychczasowego kolektora.
            # Data publikacji jest sprawdzana
            # przed zapisaniem do MySQL.
            zapisz_film(
                url=url,
                start_date=start_date,
                end_date=end_date,
            )

            saved += 1
            known_ids.add(video_id)

            logger.info(
                "NOWY FILM ZAPISANY: %s (%s/%s)",
                video_id,
                saved,
                args.max_new,
            )

        except VideoOutsideDateRange:
            skipped_date += 1

            logger.info(
                "POMINIĘTO: film poza zakresem dat – %s",
                video_id,
            )

        except ValueError as error:
            if "Brak daty publikacji" in str(error):
                missing_date += 1

                logger.warning(
                    "POMINIĘTO: brak daty publikacji – %s",
                    video_id,
                )
            else:
                errors += 1

                logger.error(
                    "BŁĄD WALIDACJI %s: %s",
                    video_id,
                    error,
                )

        except Exception:
            errors += 1

            logger.exception(
                "BŁĄD POBIERANIA FILMU %s",
                video_id,
            )

        # Ograniczamy częstotliwość odczytów.
        if (
            attempts < args.max_details
            and saved < args.max_new
        ):
            time.sleep(args.pause_videos)

    logger.info("PODSUMOWANIE KLUBU: %s", name)
    logger.info("Nowe filmy zapisane: %s", saved)
    logger.info("Próby szczegółowe: %s", attempts)
    logger.info("Poza okresem: %s", skipped_date)
    logger.info("Brak daty: %s", missing_date)
    logger.info("Błędy: %s", errors)

    if len(entries) > args.max_scanned:
        logger.warning(
            "Nie przeanalizowano całej listy profilu."
        )

    if len(candidates) > attempts:
        logger.info(
            "Pozostałe kandydatury: %s",
            len(candidates) - attempts,
        )

    return errors == 0


def main():
    parser = argparse.ArgumentParser(
        description="FSI – New Video Discovery"
    )

    parser.add_argument(
        "--handles",
        default=None,
        help="Lista handle klubów oddzielonych przecinkami",
    )

    parser.add_argument(
        "--max-clubs",
        type=int,
        default=2,
        help="Maksymalna liczba klubów",
    )

    parser.add_argument(
        "--max-scanned",
        type=int,
        default=40,
        help="Liczba pozycji listy profilu do przejrzenia",
    )

    parser.add_argument(
        "--max-new",
        type=int,
        default=3,
        help="Maksymalna liczba nowych filmów na klub",
    )

    parser.add_argument(
        "--max-details",
        type=int,
        default=10,
        help="Maksymalna liczba szczegółowych odczytów na klub",
    )

    parser.add_argument(
        "--lookback-days",
        type=int,
        default=14,
        help="Szukaj publikacji od dzisiaj minus N dni",
    )

    parser.add_argument(
        "--pause-videos",
        type=int,
        default=3,
        help="Przerwa między szczegółowymi odczytami",
    )

    parser.add_argument(
        "--pause-clubs",
        type=int,
        default=30,
        help="Przerwa pomiędzy klubami",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pokaż kandydatów bez zapisu do MySQL",
    )

    args = parser.parse_args()
    setup_logging()

    if not 1 <= args.max_clubs <= 49:
        parser.error("--max-clubs: dozwolone 1–49")

    if not 1 <= args.max_scanned <= 250:
        parser.error("--max-scanned: dozwolone 1–250")

    if not 1 <= args.max_new <= 20:
        parser.error("--max-new: dozwolone 1–20")

    if not args.max_new <= args.max_details <= 30:
        parser.error(
            "--max-details musi być >= --max-new "
            "i <= 30"
        )

    if not 1 <= args.lookback_days <= 365:
        parser.error("--lookback-days: dozwolone 1–365")

    if not 2 <= args.pause_videos <= 300:
        parser.error("--pause-videos: dozwolone 2–300")

    if not 10 <= args.pause_clubs <= 600:
        parser.error("--pause-clubs: dozwolone 10–600")

    today = datetime.now(timezone.utc).date()

    start_date = (
        today - timedelta(days=args.lookback_days)
    ).isoformat()

    end_date = today.isoformat()

    logger.info("=" * 60)
    logger.info("FSI 0.8.3 – NEW VIDEO DISCOVERY")
    logger.info("Zakres publikacji UTC: %s – %s",
                start_date, end_date)
    logger.info("Limit nowych filmów: %s", args.max_new)
    logger.info("Limit odczytów: %s", args.max_details)
    logger.info("Tryb testowy: %s", args.dry_run)
    logger.info("=" * 60)

    try:
        handles = parse_handles(args.handles)

        clubs, available_count = get_clubs(
            handles,
            args.max_clubs,
        )

    except Exception:
        logger.exception(
            "Nie udało się pobrać klubów z MySQL."
        )
        return 1

    if not clubs:
        logger.warning("Brak klubów do analizy.")
        return 0

    if available_count > len(clubs):
        logger.warning(
            "Wybrano %s z %s dostępnych klubów.",
            len(clubs),
            available_count,
        )

    failed_clubs = 0
    successful_clubs = 0

    for index, club in enumerate(clubs):
        try:
            success = discover_for_club(
                club,
                args,
                start_date,
                end_date,
            )

            if success:
                successful_clubs += 1
            else:
                failed_clubs += 1

        except Exception:
            logger.exception(
                "Nieoczekiwany błąd klubu: %s",
                club["name"],
            )
            failed_clubs += 1

        if (
            not args.dry_run
            and index < len(clubs) - 1
        ):
            logger.info(
                "Przerwa między klubami: %s sekund",
                args.pause_clubs,
            )

            time.sleep(args.pause_clubs)

    logger.info("=" * 60)
    logger.info("KONIEC NEW VIDEO DISCOVERY")
    logger.info("Kluby bez błędów: %s", successful_clubs)
    logger.info("Kluby z błędami: %s", failed_clubs)
    logger.info("=" * 60)

    return 1 if failed_clubs else 0


if __name__ == "__main__":
    sys.exit(main())
