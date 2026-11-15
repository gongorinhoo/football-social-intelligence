
import argparse
import asyncio
import json
import re
import subprocess
import sys
import time

from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from database import Base, SessionLocal
from models import Club, ProfileSnapshot, Video

BACKEND_DIR = Path(__file__).resolve().parent
LOG_DIR = BACKEND_DIR / "logs"

router = APIRouter(
    prefix="/api/web-collection",
    tags=["Web Collection Center"],
)

ALLOWED_ORIGINS = {
    "http://localhost:3000",
    "http://127.0.0.1:3000",
}


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_iso(value):
    return value.isoformat() + "Z" if value else None


class WebCollectionJob(Base):
    __tablename__ = "web_collection_jobs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default="queued", nullable=False
    )

    # UNIQUE pozwala mieć tylko jedno aktywne zadanie.
    # Zakończone zadania mają tutaj NULL.
    active_slot: Mapped[int | None] = mapped_column(
        Integer, unique=True, nullable=True
    )

    club_ids_json: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    discover_new: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    refresh_existing: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )
    collect_followers: Mapped[bool] = mapped_column(
        Boolean, nullable=False
    )

    max_scanned: Mapped[int] = mapped_column(Integer, nullable=False)
    max_details: Mapped[int] = mapped_column(Integer, nullable=False)
    max_new: Mapped[int] = mapped_column(Integer, nullable=False)
    max_existing: Mapped[int] = mapped_column(Integer, nullable=False)

    total_clubs: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    completed_clubs: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    new_videos: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    refreshed_videos: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    followers_saved: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    errors_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    message: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    worker_pid: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )


class StartCollection(BaseModel):
    all_clubs: bool = False
    club_ids: list[int] = Field(default_factory=list)

    start_date: date
    end_date: date

    discover_new: bool = True
    refresh_existing: bool = True
    collect_followers: bool = False

    max_scanned: int = Field(default=150, ge=1, le=250)
    max_details: int = Field(default=20, ge=1, le=60)
    max_new: int = Field(default=5, ge=1, le=20)
    max_existing: int = Field(default=5, ge=1, le=20)


def require_local_browser(request: Request):
    # To zabezpieczenie lokalnego środowiska,
    # nie zamiennik logowania w publicznej aplikacji.
    host = request.client.host if request.client else ""

    if host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "Dostęp tylko lokalny.")

    if request.headers.get("origin") not in ALLOWED_ORIGINS:
        raise HTTPException(
            403,
            "Żądanie nie pochodzi z lokalnej strony FSI."
        )


def job_dict(job):
    return {
        "id": job.id,
        "status": job.status,
        "start_date": job.start_date.isoformat(),
        "end_date": job.end_date.isoformat(),
        "total_clubs": job.total_clubs,
        "completed_clubs": job.completed_clubs,
        "new_videos": job.new_videos,
        "refreshed_videos": job.refreshed_videos,
        "followers_saved": job.followers_saved,
        "errors_count": job.errors_count,
        "message": job.message,
        "created_at": to_iso(job.created_at),
        "started_at": to_iso(job.started_at),
        "heartbeat_at": to_iso(job.heartbeat_at),
        "finished_at": to_iso(job.finished_at),
    }


@router.get("/clubs")
def get_available_clubs():
    with SessionLocal() as db:
        clubs = db.scalars(
            select(Club)
            .where(Club.is_active.is_(True))
            .order_by(Club.name.asc())
        ).all()

        return {
            "items": [
                {
                    "id": club.id,
                    "name": club.name,
                    "handle": club.tiktok_handle,
                }
                for club in clubs
            ]
        }


@router.get("/jobs/latest")
def get_latest_job():
    with SessionLocal() as db:
        job = db.scalar(
            select(WebCollectionJob)
            .order_by(WebCollectionJob.id.desc())
            .limit(1)
        )

        return {"job": job_dict(job) if job else None}


@router.get("/jobs/{job_id}")
def get_job(job_id: int):
    with SessionLocal() as db:
        job = db.get(WebCollectionJob, job_id)

        if job is None:
            raise HTTPException(404, "Nie znaleziono zadania.")

        return {"job": job_dict(job)}


@router.post("/jobs", status_code=202)
def start_collection(payload: StartCollection, request: Request):
    require_local_browser(request)

    if payload.start_date > payload.end_date:
        raise HTTPException(422, "Nieprawidłowy zakres dat.")

    if (payload.end_date - payload.start_date).days > 366:
        raise HTTPException(
            422, "Jedno zadanie może obejmować maksymalnie 366 dni."
        )

    if payload.end_date > datetime.now(timezone.utc).date():
        raise HTTPException(
            422, "Data końcowa nie może być w przyszłości."
        )

    if not any((
        payload.discover_new,
        payload.refresh_existing,
        payload.collect_followers,
    )):
        raise HTTPException(422, "Wybierz rodzaj pobierania.")

    if not payload.all_clubs and not payload.club_ids:
        raise HTTPException(422, "Wybierz co najmniej jeden klub.")

    requested_ids = sorted(set(payload.club_ids))

    if len(requested_ids) > 49 or any(x < 1 for x in requested_ids):
        raise HTTPException(422, "Nieprawidłowa lista klubów.")

    try:
        with SessionLocal.begin() as db:
            query = select(Club.id).where(
                Club.is_active.is_(True)
            )

            if not payload.all_clubs:
                query = query.where(Club.id.in_(requested_ids))

            ids = sorted(db.scalars(query).all())

            if not ids:
                raise HTTPException(
                    422, "Nie znaleziono aktywnych klubów."
                )

            if not payload.all_clubs and ids != requested_ids:
                raise HTTPException(
                    422, "Niektóre wybrane kluby są nieaktywne."
                )

            if db.scalar(
                select(WebCollectionJob.id)
                .where(WebCollectionJob.active_slot == 1)
            ) is not None:
                raise HTTPException(
                    409, "Inne zadanie pobierania już trwa."
                )

            job = WebCollectionJob(
                status="queued",
                active_slot=1,
                club_ids_json=json.dumps(ids),
                start_date=payload.start_date,
                end_date=payload.end_date,
                discover_new=payload.discover_new,
                refresh_existing=payload.refresh_existing,
                collect_followers=payload.collect_followers,
                max_scanned=payload.max_scanned,
                max_details=payload.max_details,
                max_new=payload.max_new,
                max_existing=payload.max_existing,
                total_clubs=len(ids),
                message="Oczekiwanie na uruchomienie procesu.",
                heartbeat_at=utc_now(),
            )

            db.add(job)
            db.flush()
            job_id = job.id

    except IntegrityError as error:
        raise HTTPException(
            409, "Inne zadanie zostało właśnie uruchomione."
        ) from error

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"fsi_web_job_{job_id}.log"

    try:
        command = [
            sys.executable,
            "-u",
            "-m",
            "web_collection_worker",
            "--worker-job",
            str(job_id),
        ]

        with log_path.open("a", encoding="utf-8") as logfile:
            process = subprocess.Popen(
                command,
                cwd=str(BACKEND_DIR),
                stdout=logfile,
                stderr=subprocess.STDOUT,
                creationflags=(
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    if sys.platform == "win32"
                    else 0
                ),
            )

        with SessionLocal.begin() as db:
            job = db.get(WebCollectionJob, job_id)
            job.worker_pid = process.pid

    except Exception as error:
        with SessionLocal.begin() as db:
            job = db.get(WebCollectionJob, job_id)
            job.status = "failed"
            job.active_slot = None
            job.finished_at = utc_now()
            job.message = "Nie udało się uruchomić procesu."

        raise HTTPException(
            500, "Błąd uruchamiania zadania."
        ) from error

    return {"job_id": job_id, "status": "queued"}


def update_job(job_id, message=None, **increments):
    with SessionLocal.begin() as db:
        job = db.get(WebCollectionJob, job_id)

        if job is None:
            raise RuntimeError("Zadanie nie istnieje.")

        for name, amount in increments.items():
            setattr(job, name, getattr(job, name) + amount)

        if message is not None:
            job.message = message[:500]

        job.heartbeat_at = utc_now()


def count_followers(club_id):
    with SessionLocal() as db:
        return db.scalar(
            select(func.count(ProfileSnapshot.id))
            .where(ProfileSnapshot.club_id == club_id)
        ) or 0


def approximate_video_date(video_id):
    """
    Data orientacyjna z identyfikatora TikTok.
    Używamy jej WYŁĄCZNIE do kolejności sprawdzania.
    Ostateczna walidacja odbywa się przez yt-dlp.
    """
    try:
        timestamp = int(video_id) >> 32
        return datetime.fromtimestamp(
            timestamp, timezone.utc
        ).date()
    except (ValueError, OverflowError, OSError):
        return None


def prioritize_candidates(candidates, start, end):
    def distance(video_id):
        estimated = approximate_video_date(video_id)

        if estimated is None:
            return 999999

        if start <= estimated <= end:
            return 0

        if estimated < start:
            return (start - estimated).days

        return (estimated - end).days

    return sorted(candidates, key=distance)

def is_cancel_requested(job_id):
    with SessionLocal() as db:
        status = db.scalar(
            select(WebCollectionJob.status)
            .where(WebCollectionJob.id == job_id)
        )

        return status == "cancel_requested"

def process_club(job_id, job, club):
    from collectors.tiktok_followers import wykonaj_pomiar
    from collectors.tiktok_videos import (
        zapisz_film,
        VideoOutsideDateRange,
    )
    from collectors.tiktok_profile_videos import (
        pobierz_liste_filmow,
    )

    handle = club.tiktok_handle
    errors = 0

    start_dt = datetime.combine(job.start_date, dt_time.min)
    end_dt = datetime.combine(
        job.end_date + timedelta(days=1), dt_time.min
    )

    with SessionLocal() as db:
        known_ids = set(db.scalars(
            select(Video.tiktok_video_id)
            .where(Video.club_id == club.id)
        ).all())

        existing = db.execute(
            select(Video.url, Video.tiktok_video_id)
            .where(
                Video.club_id == club.id,
                Video.published_at >= start_dt,
                Video.published_at < end_dt,
            )
            .order_by(Video.published_at.desc())
            .limit(job.max_existing)
        ).all()

    # Opcjonalny aktualny pomiar obserwujących.
    if job.collect_followers and not is_cancel_requested(job_id):
        update_job(
            job_id,
            message=f"{club.name}: pobieranie obserwujących",
        )
        before = count_followers(club.id)

        try:
            asyncio.run(wykonaj_pomiar(handle))

            if count_followers(club.id) > before:
                update_job(job_id, followers_saved=1)
            else:
                errors += 1
                print("Nie zapisano pomiaru obserwujących.")
        except Exception as error:
            errors += 1
            print(f"Błąd obserwujących @{handle}: {error}")

    # Wykrywanie filmów jeszcze nieznanych w MySQL.
    if job.discover_new and not is_cancel_requested(job_id):
        update_job(
            job_id,
            message=f"{club.name}: sprawdzanie listy filmów",
        )

        try:
            entries = pobierz_liste_filmow(handle)
            candidates = []
            seen = set()

            # Limit dotyczy liczby pozycji z profilu.
            for entry in entries[:job.max_scanned]:
                if not isinstance(entry, dict):
                    continue

                video_id = str(entry.get("id") or "")

                if not re.fullmatch(r"\d{16,22}", video_id):
                    continue

                if video_id in known_ids or video_id in seen:
                    continue

                seen.add(video_id)
                candidates.append(video_id)

            candidates = prioritize_candidates(
                candidates, job.start_date, job.end_date
            )

            saved = 0

            for index, video_id in enumerate(
                candidates[:job.max_details]
            ):
                if is_cancel_requested(job_id):
                    print("Przerwano wykrywanie nowych filmów.")
                    break

                if saved >= job.max_new:
                    break

                update_job(
                    job_id,
                    message=f"{club.name}: sprawdzanie filmu {index + 1}",
                )

                url = (
                    f"https://www.tiktok.com/"
                    f"@{handle}/video/{video_id}"
                )

                try:
                    zapisz_film(
                        url=url,
                        start_date=job.start_date.isoformat(),
                        end_date=job.end_date.isoformat(),
                    )
                    saved += 1
                    known_ids.add(video_id)
                    update_job(job_id, new_videos=1)

                except VideoOutsideDateRange:
                    # Film spoza okresu to nie awaria.
                    pass

                except ValueError as error:
                    if "Brak daty publikacji" not in str(error):
                        errors += 1
                        print(f"Błąd filmu {video_id}: {error}")

                except Exception as error:
                    errors += 1
                    print(f"Błąd filmu {video_id}: {error}")

                time.sleep(2)

            if len(entries) > job.max_scanned:
                print(
                    f"Uwaga: sprawdzono tylko pierwsze "
                    f"{job.max_scanned} pozycji profilu."
                )

        except Exception as error:
            errors += 1
            print(f"Błąd listy filmów @{handle}: {error}")

    # Nowe snapshoty filmów już zapisanych w bazie.
    if job.refresh_existing and not is_cancel_requested(job_id):
        for index, (url, video_id) in enumerate(existing):
                
            if is_cancel_requested(job_id):
                print("Przerwano odświeżanie filmów.")
                break

            update_job(
                job_id,
                message=f"{club.name}: odświeżanie filmu {index + 1}",
            )

            try:
                zapisz_film(
                    url=url,
                    start_date=job.start_date.isoformat(),
                    end_date=job.end_date.isoformat(),
                )
                update_job(job_id, refreshed_videos=1)
            except Exception as error:
                errors += 1
                print(f"Błąd odświeżania {video_id}: {error}")

            time.sleep(2)

    return errors



def run_worker(job_id):
    from collection_job_management import WebCollectionJobClub

    # Rozpoczęcie zadania
    with SessionLocal.begin() as db:
        job = db.get(WebCollectionJob, job_id)

        if job is None:
            return 1

        # Anulowanie mogło nastąpić, zanim worker wystartował.
        if job.status == "cancel_requested":
            job.status = "cancelled"
            job.active_slot = None
            job.finished_at = utc_now()
            job.heartbeat_at = utc_now()
            job.message = "Anulowano przed rozpoczęciem."
            return 0

        if job.status != "queued":
            return 1

        job.status = "running"
        job.started_at = utc_now()
        job.heartbeat_at = utc_now()
        job.message = "Rozpoczynam pobieranie."

    try:
        # Pobieramy listę klubów z zadania.
        with SessionLocal() as db:
            job = db.get(WebCollectionJob, job_id)

            ids = json.loads(job.club_ids_json)

            clubs = db.scalars(
                select(Club)
                .where(
                    Club.id.in_(ids),
                    Club.is_active.is_(True),
                )
                .order_by(Club.name.asc())
            ).all()

            for club in clubs:
                db.expunge(club)

        for index, club in enumerate(clubs):

            # Nie rozpoczynamy kolejnego klubu po anulowaniu.
            if is_cancel_requested(job_id):
                print("Zadanie anulowane przed kolejnym klubem.")
                break

            print(
                f"\n=== {club.name} "
                f"(@{club.tiktok_handle}) ===",
                flush=True,
            )

            # Zapisujemy rozpoczęcie obsługi danego klubu
            # oraz liczniki sprzed przetwarzania.
            with SessionLocal.begin() as db:
                job = db.get(WebCollectionJob, job_id)

                before_new = job.new_videos
                before_refreshed = job.refreshed_videos
                before_followers = job.followers_saved

                club_result = WebCollectionJobClub(
                    job_id=job_id,
                    club_id=club.id,
                    club_name=club.name,
                    status="running",
                    started_at=utc_now(),
                    message="Rozpoczęto pobieranie.",
                )

                db.add(club_result)
                db.flush()
                result_id = club_result.id

            update_job(
                job_id,
                message=(
                    f"Klub {index + 1}/{len(clubs)}: "
                    f"{club.name}"
                ),
            )

            errors = 0

            try:
                with SessionLocal() as db:
                    job = db.get(WebCollectionJob, job_id)

                    errors = process_club(
                        job_id,
                        job,
                        club,
                    )

            except Exception as error:
                errors = 1
                print(
                    f"Błąd przetwarzania klubu: {error}",
                    flush=True,
                )

            # Zapisujemy szczegółowe wyniki tego klubu.
            with SessionLocal.begin() as db:
                job = db.get(WebCollectionJob, job_id)
                club_result = db.get(
                    WebCollectionJobClub,
                    result_id,
                )

                club_result.new_videos = max(
                    0,
                    job.new_videos - before_new,
                )

                club_result.refreshed_videos = max(
                    0,
                    job.refreshed_videos - before_refreshed,
                )

                club_result.followers_saved = max(
                    0,
                    job.followers_saved - before_followers,
                )

                club_result.errors_count = errors
                club_result.finished_at = utc_now()

                if job.status == "cancel_requested":
                    club_result.status = "cancelled"
                    club_result.message = (
                        "Przerwano na żądanie użytkownika."
                    )
                elif errors > 0:
                    club_result.status = "partial"
                    club_result.message = (
                        "Zakończono z błędami."
                    )
                else:
                    club_result.status = "completed"
                    club_result.message = (
                        "Zakończono poprawnie."
                    )

                job.completed_clubs += 1
                job.errors_count += errors
                job.heartbeat_at = utc_now()

            if is_cancel_requested(job_id):
                break

            if index < len(clubs) - 1:
                time.sleep(10)

        # Końcowe podsumowanie całego zadania.
        with SessionLocal.begin() as db:
            job = db.get(WebCollectionJob, job_id)

            if job.status == "cancel_requested":
                job.status = "cancelled"
                job.message = (
                    "Zadanie anulowano. "
                    "Zachowano wcześniej zapisane dane."
                )

            elif job.errors_count > 0:
                job.status = "partial"
                job.message = (
                    "Zakończono z błędami."
                )

            else:
                job.status = "completed"
                job.message = (
                    "Zakończono zbieranie danych."
                )

            job.active_slot = None
            job.finished_at = utc_now()
            job.heartbeat_at = utc_now()

        return 0

    except Exception as error:
        print(
            f"KRYTYCZNY BŁĄD ZADANIA: {error}",
            flush=True,
        )

        with SessionLocal.begin() as db:
            job = db.get(WebCollectionJob, job_id)

            if job is not None:
                job.status = "failed"
                job.active_slot = None
                job.finished_at = utc_now()
                job.heartbeat_at = utc_now()
                job.errors_count += 1
                job.message = (
                    "Zadanie przerwane błędem."
                )

        return 1



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-job", type=int, required=True)
    args = parser.parse_args()

    sys.exit(run_worker(args.worker_job))
