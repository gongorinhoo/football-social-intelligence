
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from database import SessionLocal
from models import Club, ProfileSnapshot, Video, VideoSnapshot


router = APIRouter(
    prefix="/api/monitoring",
    tags=["Collection Monitoring"],
)

BACKEND_DIR = Path(__file__).resolve().parent
LOGS_DIR = BACKEND_DIR / "logs"

LOG_FILES = [
    "fsi_daily.log",
    "fsi_multi.log",
    "fsi_discovery.log",
]

LOG_PATTERN = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?)"
    r" \| (ERROR|WARNING) \| (.*)$"
)


def to_utc_iso(value):
    """Zwraca datę w formacie ISO UTC."""
    if value is None:
        return None

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return (
        value.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def get_freshness_status(last_at, cutoff):
    """
    recent  - pomiar mieści się w wybranym limicie
    stale   - pomiar jest starszy
    missing - nie ma pomiaru
    """
    if last_at is None:
        return "missing"

    if last_at >= cutoff:
        return "recent"

    return "stale"


def get_log_data():
    """
    Czyta końcowe fragmenty znanych plików logów.

    Nie udostępnia całych logów ani tracebacków.
    Do API trafiają tylko krótkie komunikaty
    ERROR i WARNING.
    """
    log_files = []
    events = []

    for filename in LOG_FILES:
        path = LOGS_DIR / filename

        if not path.is_file():
            log_files.append({
                "name": filename,
                "exists": False,
                "updated_at": None,
                "read_error": False,
            })
            continue

        try:
            modified_at = datetime.fromtimestamp(
                path.stat().st_mtime,
                timezone.utc,
            )

            log_files.append({
                "name": filename,
                "exists": True,
                "updated_at": to_utc_iso(modified_at),
                "read_error": False,
            })

            with path.open(
                "r",
                encoding="utf-8",
                errors="replace",
            ) as file:
                recent_lines = deque(file, maxlen=300)

            for line in recent_lines:
                match = LOG_PATTERN.match(line.strip())

                if not match:
                    continue

                timestamp, level, message = match.groups()

                # Usuwamy ewentualne wartości sekretów.
                message = re.sub(
                    r"(?i)\b(password|token|authorization|"
                    r"cookie|secret|api[_-]?key)\b"
                    r"\s*[:=]\s*\S+",
                    r"\1=[UKRYTE]",
                    message,
                )

                events.append({
                    "source": filename,
                    "time_local": timestamp,
                    "level": level,
                    "message": message[:180],
                })

        except OSError:
            log_files.append({
                "name": filename,
                "exists": True,
                "updated_at": None,
                "read_error": True,
            })

    # Wszystkie logi pochodzą z tego samego komputera.
    events.sort(
        key=lambda event: event["time_local"],
        reverse=True,
    )

    return {
        "files": log_files,
        "recent_events": events[:15],
    }


@router.get("/overview")
def get_collection_monitoring(
    hours: int = Query(48, ge=1, le=720),
):
    """
    Monitoring świeżości danych dla aktywnych klubów.

    Nie jest to bezpośredni odczyt stanu
    Harmonogramu zadań Windows.
    """
    now = datetime.now(timezone.utc)
    cutoff = (
        now - timedelta(hours=hours)
    ).replace(tzinfo=None)

    try:
        with SessionLocal() as db:

            clubs = db.scalars(
                select(Club)
                .where(Club.is_active.is_(True))
                .order_by(Club.name.asc())
            ).all()

            # Pomiar obserwujących:
            # tylko rekordy z rzeczywistą liczbą.
            follower_rows = db.execute(
                select(
                    ProfileSnapshot.club_id,
                    func.count(ProfileSnapshot.id),
                    func.max(ProfileSnapshot.collected_at),
                )
                .where(
                    ProfileSnapshot.followers_count.is_not(None)
                )
                .group_by(ProfileSnapshot.club_id)
            ).all()

            # Liczba znanych filmów każdego klubu.
            video_rows = db.execute(
                select(
                    Video.club_id,
                    func.count(Video.id),
                )
                .group_by(Video.club_id)
            ).all()

            # Pomiar filmów:
            # liczymy wszystkie zapisane snapshoty.
            video_snapshot_rows = db.execute(
                select(
                    Video.club_id,
                    func.count(VideoSnapshot.id),
                    func.count(
                        func.distinct(VideoSnapshot.video_id)
                    ),
                    func.max(VideoSnapshot.collected_at),
                )
                .select_from(VideoSnapshot)
                .join(
                    Video,
                    Video.id == VideoSnapshot.video_id,
                )
                .group_by(Video.club_id)
            ).all()

            followers_by_club = {
                club_id: {
                    "count": int(count),
                    "last": last_at,
                }
                for club_id, count, last_at in follower_rows
            }

            videos_by_club = {
                club_id: int(count)
                for club_id, count in video_rows
            }

            snapshots_by_club = {
                club_id: {
                    "count": int(count),
                    "measured_videos": int(measured),
                    "last": last_at,
                }
                for club_id, count, measured, last_at
                in video_snapshot_rows
            }

            club_items = []

            for club in clubs:
                followers = followers_by_club.get(
                    club.id,
                    {"count": 0, "last": None},
                )

                video_data = snapshots_by_club.get(
                    club.id,
                    {
                        "count": 0,
                        "measured_videos": 0,
                        "last": None,
                    },
                )

                known_videos = videos_by_club.get(
                    club.id,
                    0,
                )

                followers_status = get_freshness_status(
                    followers["last"],
                    cutoff,
                )

                videos_status = get_freshness_status(
                    video_data["last"],
                    cutoff,
                )

                club_items.append({
                    "club_id": club.id,
                    "name": club.name,
                    "tiktok_handle": club.tiktok_handle,

                    "followers_status": followers_status,
                    "followers_last_at": to_utc_iso(
                        followers["last"]
                    ),
                    "followers_measurements": followers["count"],

                    "videos_status": videos_status,
                    "videos_last_at": to_utc_iso(
                        video_data["last"]
                    ),
                    "known_videos": known_videos,
                    "measured_videos": video_data["measured_videos"],
                    "video_measurements": video_data["count"],
                })

    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail="Nie udało się odczytać danych monitoringu z MySQL.",
        ) from error

    summary = {
        "active_clubs": len(club_items),

        "followers_recent": sum(
            item["followers_status"] == "recent"
            for item in club_items
        ),

        "followers_stale": sum(
            item["followers_status"] == "stale"
            for item in club_items
        ),

        "followers_missing": sum(
            item["followers_status"] == "missing"
            for item in club_items
        ),

        "videos_recent": sum(
            item["videos_status"] == "recent"
            for item in club_items
        ),

        "videos_stale": sum(
            item["videos_status"] == "stale"
            for item in club_items
        ),

        "videos_missing": sum(
            item["videos_status"] == "missing"
            for item in club_items
        ),

        "known_videos_total": sum(
            item["known_videos"]
            for item in club_items
        ),

        "video_measurements_total": sum(
            item["video_measurements"]
            for item in club_items
        ),
    }

    return {
        "generated_at": to_utc_iso(now),
        "threshold_hours": hours,
        "summary": summary,
        "clubs": club_items,
        "logs": get_log_data(),
    }
