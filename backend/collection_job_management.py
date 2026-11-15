
from datetime import datetime, timedelta, timezone

import psutil

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base, SessionLocal
from web_collection_routes import (
    WebCollectionJob,
    job_dict,
    require_local_browser,
    utc_now,
    to_iso,
)


router = APIRouter(
    prefix="/api/web-collection/management",
    tags=["Collection Job Management"],
)


class WebCollectionJobClub(Base):
    __tablename__ = "web_collection_job_clubs"

    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "club_id",
            name="uq_web_job_club",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    job_id: Mapped[int] = mapped_column(
        ForeignKey("web_collection_jobs.id"),
        nullable=False,
    )

    club_id: Mapped[int] = mapped_column(
        ForeignKey("clubs.id"),
        nullable=False,
    )

    club_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="running",
    )

    new_videos: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    refreshed_videos: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    followers_saved: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    errors_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=utc_now,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    message: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )


ACTIVE_STATUSES = {
    "queued",
    "running",
    "cancel_requested",
}

FINAL_STATUSES = {
    "completed",
    "partial",
    "failed",
    "cancelled",
    "interrupted",
}


def club_dict(item):
    return {
        "id": item.id,
        "club_id": item.club_id,
        "club_name": item.club_name,
        "status": item.status,
        "new_videos": item.new_videos,
        "refreshed_videos": item.refreshed_videos,
        "followers_saved": item.followers_saved,
        "errors_count": item.errors_count,
        "message": item.message,
        "started_at": to_iso(item.started_at),
        "finished_at": to_iso(item.finished_at),
    }


def matches_worker_command(command, job_id):
    """
    Weryfikuje argumenty uruchomienia procesu.
    Nie zakładamy, że sam numer PID wystarcza.
    """
    if not command:
        return False

    try:
        index = command.index("--worker-job")
    except ValueError:
        return False

    if index + 1 >= len(command):
        return False

    return (
        command[index + 1] == str(job_id)
        and any(
            module in command
            for module in (
                "web_collection_worker",
                "web_collection_routes",
            )
            )
    )


def worker_state(job_id, worker_pid):
    """
    alive   - znaleziono proces właściwego zadania
    absent  - proces nie istnieje
    unknown - brak wystarczających uprawnień
    """

    if worker_pid:
        try:
            process = psutil.Process(worker_pid)

            if not process.is_running():
                return "absent"

            command = process.cmdline()

            if matches_worker_command(command, job_id):
                return "alive"

            # PID może należeć już do innego procesu.
            return "absent"

        except psutil.NoSuchProcess:
            return "absent"

        except psutil.AccessDenied:
            return "unknown"

    # Awaria mogła nastąpić zanim zapisano PID.
    # Szukamy wtedy procesu po argumentach.
    uncertain = False

    for process in psutil.process_iter(["cmdline"]):
        try:
            command = process.info.get("cmdline") or []

            if matches_worker_command(command, job_id):
                return "alive"

        except psutil.NoSuchProcess:
            continue

        except psutil.AccessDenied:
            uncertain = True

    return "unknown" if uncertain else "absent"


@router.get("/jobs")
def list_jobs(
    limit: int = Query(30, ge=1, le=100),
):
    with SessionLocal() as db:
        jobs = db.scalars(
            select(WebCollectionJob)
            .order_by(WebCollectionJob.id.desc())
            .limit(limit)
        ).all()

        return {
            "items": [job_dict(job) for job in jobs]
        }


@router.get("/jobs/{job_id}")
def get_job_details(job_id: int):
    with SessionLocal() as db:
        job = db.get(WebCollectionJob, job_id)

        if job is None:
            raise HTTPException(
                404,
                "Nie znaleziono zadania.",
            )

        clubs = db.scalars(
            select(WebCollectionJobClub)
            .where(WebCollectionJobClub.job_id == job_id)
            .order_by(WebCollectionJobClub.id.asc())
        ).all()

        state = (
            worker_state(job.id, job.worker_pid)
            if job.status in ACTIVE_STATUSES
            else "not_applicable"
        )

        return {
            "job": job_dict(job),
            "worker_state": state,
            "clubs": [club_dict(item) for item in clubs],
        }


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: int, request: Request):
    require_local_browser(request)

    with SessionLocal.begin() as db:
        job = db.scalar(
            select(WebCollectionJob)
            .where(WebCollectionJob.id == job_id)
            .with_for_update()
        )

        if job is None:
            raise HTTPException(
                404,
                "Nie znaleziono zadania.",
            )

        if job.status == "cancel_requested":
            return {
                "status": job.status,
                "message": "Anulowanie już zostało zlecone.",
            }

        if job.status not in {"queued", "running"}:
            raise HTTPException(
                409,
                "Tego zadania nie można już anulować.",
            )

        job.status = "cancel_requested"
        job.message = (
            "Zgłoszono anulowanie. "
            "Oczekiwanie na bezpieczny punkt zatrzymania."
        )

        return {
            "status": "cancel_requested",
            "message": job.message,
        }


@router.post("/jobs/{job_id}/recover")
def recover_interrupted_job(
    job_id: int,
    request: Request,
):
    """
    Odblokowuje kolejkę wyłącznie wtedy, gdy
    nie ma aktywnego procesu danego zadania.

    Nie uruchamia ponownie zbierania danych.
    """
    require_local_browser(request)

    with SessionLocal() as db:
        job = db.get(WebCollectionJob, job_id)

        if job is None:
            raise HTTPException(
                404,
                "Nie znaleziono zadania.",
            )

        if job.status not in ACTIVE_STATUSES:
            raise HTTPException(
                409,
                "Zadanie nie jest aktywne.",
            )

        # Nie diagnozujemy jako awarii zadania,
        # które może dopiero się uruchamiać.
        reference_time = (
            job.heartbeat_at or job.created_at
        )

        if utc_now() - reference_time < timedelta(minutes=5):
            raise HTTPException(
                409,
                "Zadanie było aktywne niedawno. "
                "Sprawdź je ponownie później.",
            )

        state = worker_state(
            job.id,
            job.worker_pid,
        )

        if state == "alive":
            raise HTTPException(
                409,
                "Proces nadal działa. "
                "Nie można odblokować kolejki.",
            )

        if state == "unknown":
            raise HTTPException(
                409,
                "Nie można potwierdzić zakończenia procesu.",
            )

    # Ponowna kontrola stanu wewnątrz transakcji.
    with SessionLocal.begin() as db:
        job = db.scalar(
            select(WebCollectionJob)
            .where(WebCollectionJob.id == job_id)
            .with_for_update()
        )

        if job is None or job.status not in ACTIVE_STATUSES:
            raise HTTPException(
                409,
                "Stan zadania uległ zmianie.",
            )

        # Zabezpieczenie przed zmianą aktywności
        # między sprawdzeniem a aktualizacją.
        if (
            job.heartbeat_at is not None
            and utc_now() - job.heartbeat_at
            < timedelta(minutes=5)
        ):
            raise HTTPException(
                409,
                "Zadanie zgłosiło nową aktywność.",
            )

        if worker_state(job.id, job.worker_pid) != "absent":
            raise HTTPException(
                409,
                "Nie potwierdzono zakończenia procesu.",
            )

        job.status = "interrupted"
        job.active_slot = None
        job.finished_at = utc_now()
        job.message = (
            "Proces zakończył się bez zapisania wyniku. "
            "Kolejka została odblokowana."
        )

        club_rows = db.scalars(
            select(WebCollectionJobClub)
            .where(
                WebCollectionJobClub.job_id == job_id,
                WebCollectionJobClub.status == "running",
            )
        ).all()

        for item in club_rows:
            item.status = "interrupted"
            item.finished_at = utc_now()
            item.message = "Przerwano podczas obsługi klubu."

    return {
        "status": "interrupted",
        "message": "Kolejka została bezpiecznie odblokowana.",
    }
