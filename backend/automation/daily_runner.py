import argparse
import asyncio
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
import traceback

from sqlalchemy import func, select

from collectors.tiktok_followers import wykonaj_pomiar
from collectors.tiktok_videos import zapisz_film
from database import SessionLocal
from models import Club, ProfileSnapshot, Video


BACKEND_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = BACKEND_DIR / "logs"


class Tee:
    """Zapisuje standardowe komunikaty do terminala i pliku logu."""

    def __init__(self, *streams):
        self.streams = streams

    def write(self, message):
        for stream in self.streams:
            stream.write(message)
        return len(message)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def log(message: str) -> None:
    current_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{current_utc}] {message}", flush=True)


def count_profile_snapshots(club_id: int) -> int:
    with SessionLocal() as db:
        return db.scalar(
            select(func.count(ProfileSnapshot.id)).where(
                ProfileSnapshot.club_id == club_id
            )
        ) or 0


def get_club_and_videos(handle: str, limit: int):
    """Zwraca klub i kilka najnowszych, JUŻ ZNANYCH filmów."""
    with SessionLocal() as db:
        club = db.scalar(
            select(Club).where(
                Club.tiktok_handle == handle,
                Club.is_active.is_(True)
            )
        )
        if club is None:
            raise ValueError(f"Nie znaleziono aktywnego klubu @{handle} w MySQL")

        video_rows = db.execute(
            select(Video.id, Video.url)
            .where(Video.club_id == club.id)
            .order_by(Video.published_at.desc(), Video.id.desc())
            .limit(limit)
        ).all()
        return club.id, club.name, [(id_, url) for id_, url in video_rows]


def run_job(args) -> int:
    club_id, club_name, videos = get_club_and_videos(
        args.handle, args.max_videos
    )
    log(f"START: {club_name} (@{args.handle}), tryb={args.mode}")
    log(f"Ostatnio zebrane filmy do odświeżenia: {len(videos)}")

    if args.dry_run:
        log("TRYB TESTOWY --dry-run: nie otwieram TikToka i niczego nie zapisuję")
        if args.mode in ("followers", "both"):
            log("Plan: jeden odczyt obserwujących")
        if args.mode in ("videos", "both"):
            for video_id, url in videos:
                log(f"Plan: odczyt filmu MySQL #{video_id} – {url}")
            if not videos:
                log("Brak filmów w bazie; najpierw uruchom kolektor profilu")
        return 0

    failures = 0
    follower_saved = False
    videos_saved = 0

    if args.mode in ("followers", "both"):
        log("Pobieram obserwujących...")
        try:
            before = count_profile_snapshots(club_id)
            asyncio.run(wykonaj_pomiar(args.handle))
            after = count_profile_snapshots(club_id)
            follower_saved = after > before
            if follower_saved:
                log("OK: nowy pomiar obserwujących jest w MySQL")
            else:
                failures += 1
                log("BŁĄD: nie pojawił się nowy pomiar obserwujących")
        except Exception:
            failures += 1
            log("BŁĄD pobierania obserwujących:")
            traceback.print_exc()

    if args.mode in ("videos", "both"):
        if not videos:
            log("INFO: brak znanych filmów do odświeżenia (nie jest to awaria)")
        else:
            for index, (video_id, url) in enumerate(videos, start=1):
                log(f"Odczyt filmu {index}/{len(videos)} (MySQL #{video_id})")
                try:
                    zapisz_film(url=url)
                    videos_saved += 1
                    log(f"OK: zapisano nowy pomiar filmu #{video_id}")
                except Exception:
                    failures += 1
                    log(f"BŁĄD filmu #{video_id}:")
                    traceback.print_exc()

                if index < len(videos):
                    time.sleep(args.delay)

    log(
        "KONIEC: "
        f"obserwujący_zapisani={follower_saved}, "
        f"pomiary_filmów={videos_saved}, błędy={failures}"
    )
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="FSI – zaplanowany odczyt TikToka")
    parser.add_argument("--handle", required=True, help="Handle z tabeli clubs")
    parser.add_argument(
        "--mode", choices=("followers", "videos", "both"), default="both"
    )
    parser.add_argument(
        "--max-videos", type=int, default=3,
        help="Ile najnowszych zapisanych filmów odświeżyć (1–10)"
    )
    parser.add_argument(
        "--delay", type=int, default=3,
        help="Odstęp między filmami w sekundach (minimum 2)"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not 1 <= args.max_videos <= 10:
        parser.error("--max-videos musi mieścić się w przedziale 1–10")
    if args.delay < 2:
        parser.error("--delay musi wynosić co najmniej 2 sekundy")

    LOG_DIR.mkdir(exist_ok=True)
    filename = datetime.now().strftime("fsi_daily_%Y%m%d_%H%M%S_%f.log")
    logfile = LOG_DIR / filename

    with logfile.open("w", encoding="utf-8") as output:
        with redirect_stdout(Tee(sys.stdout, output)), redirect_stderr(
            Tee(sys.stderr, output)
        ):
            log(f"LOG: {logfile}")
            try:
                return run_job(args)
            except Exception:
                log("BŁĄD KRYTYCZNY: zadanie nie zostało zakończone")
                traceback.print_exc()
                return 1


if __name__ == "__main__":
    raise SystemExit(main())