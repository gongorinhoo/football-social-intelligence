
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text, desc
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Club, ProfileSnapshot

from datetime import date, datetime, time, timedelta
from fastapi import Query
from sqlalchemy import func
from models import Video, VideoSnapshot

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("FSI: Inicjalizacja bazy danych...")
    
    Base.metadata.create_all(bind=engine)
    
    print("FSI: Baza danych została sprawdzona.")
    yield


app = FastAPI(
    title="Football Social Intelligence API",
    description="Backend platformy analitycznej polskiego futbolu",
    version="0.2.0",
    lifespan=lifespan
)


# Połączenie z frontendem Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {
        "project": "Football Social Intelligence",
        "status": "online",
        "version": "0.2.0"
    }


# Test połączenia z MySQL
@app.get("/health/db")
def database_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))

    return {
        "database": "connected",
        "status": "ok"
    }


# Pobieranie klubów
@app.get("/api/clubs")
def get_clubs(db: Session = Depends(get_db)):
    clubs = db.scalars(
        select(Club).order_by(Club.name)
    ).all()

    return [
        {
            "id": club.id,
            "name": club.name,
            "tiktok_handle": club.tiktok_handle,
            "league": club.league,
            "is_active": club.is_active
        }
        for club in clubs
    ]

# Pobieranie szczegółów jednego klubu
@app.get("/api/clubs/{club_id}")
def get_club(
    club_id: int,
    db: Session = Depends(get_db)
):
    club = db.get(Club, club_id)

    if club is None:
        raise HTTPException(
            status_code=404,
            detail="Nie znaleziono klubu"
        )

    return {
        "id": club.id,
        "name": club.name,
        "tiktok_handle": club.tiktok_handle,
        "league": club.league,
        "is_active": club.is_active,
        "created_at": club.created_at.isoformat()
    }


@app.get("/api/clubs/{club_id}/followers")
def get_club_followers(
    club_id: int,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    club = db.get(Club, club_id)

    if club is None:
        raise HTTPException(
            status_code=404,
            detail="Nie znaleziono klubu"
        )

    limit = max(1, min(limit, 1000))

    snapshots = db.scalars(
        select(ProfileSnapshot)
        .where(ProfileSnapshot.club_id == club_id)
        .order_by(desc(ProfileSnapshot.collected_at),
                  desc(ProfileSnapshot.id))
        .limit(limit)
    ).all()

    history = [
        {
            "id": snapshot.id,
            "followers_count": snapshot.followers_count,
            "likes_count": snapshot.likes_count,
            "collected_at": snapshot.collected_at.isoformat() + "Z"
        }
        for snapshot in reversed(snapshots)
    ]

    latest = history[-1] if history else None

    # Porównanie dwóch ostatnich dostępnych pomiarów
    growth = None

    if len(history) >= 2:
        previous = history[-2]
        current = history[-1]

        if (
            current["followers_count"] is not None
            and previous["followers_count"] is not None
        ):
            growth = (
                current["followers_count"]
                - previous["followers_count"]
            )

    return {
        "club_id": club.id,
        "club_name": club.name,
        "tiktok_handle": club.tiktok_handle,
        "latest": latest,
        "growth_since_previous_snapshot": growth,
        "history": history
    }


@app.get("/api/clubs/{club_id}/videos")
def get_club_videos(
    club_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db)
):
    club = db.get(Club, club_id)

    if club is None:
        raise HTTPException(
            status_code=404,
            detail="Nie znaleziono klubu"
        )

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="Data początkowa jest późniejsza od końcowej"
        )

    # Wybieramy najnowszy pomiar każdego filmu.
    # Drugie sortowanie po ID rozstrzyga identyczne daty.
    latest_snapshot_id = (
        select(VideoSnapshot.id)
        .where(VideoSnapshot.video_id == Video.id)
        .order_by(
            VideoSnapshot.collected_at.desc(),
            VideoSnapshot.id.desc()
        )
        .limit(1)
        .correlate(Video)
        .scalar_subquery()
    )

    filters = [Video.club_id == club_id]

    if start_date:
        filters.append(
            Video.published_at >= datetime.combine(
                start_date, time.min
            )
        )

    if end_date:
        filters.append(
            Video.published_at < datetime.combine(
                end_date + timedelta(days=1),
                time.min
            )
        )

    def latest_query(*columns):
        return (
            select(*columns)
            .select_from(Video)
            .outerjoin(
                VideoSnapshot,
                VideoSnapshot.id == latest_snapshot_id
            )
            .where(*filters)
        )

    # Statystyki dla całego wybranego okresu,
    # a nie tylko bieżącej strony tabeli.
    summary = db.execute(
        latest_query(
            func.count(Video.id),
            func.count(VideoSnapshot.views_count),
            func.sum(VideoSnapshot.views_count),
            func.sum(VideoSnapshot.likes_count),
            func.sum(VideoSnapshot.comments_count),
            func.sum(VideoSnapshot.shares_count)
        )
    ).one()

    total = int(summary[0] or 0)
    videos_with_views = int(summary[1] or 0)

    # Paginacja
    rows = db.execute(
        latest_query(Video, VideoSnapshot)
        .order_by(
            Video.published_at.desc(),
            Video.id.desc()
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []

    for video, snapshot in rows:
        items.append({
            "id": video.id,
            "tiktok_video_id": video.tiktok_video_id,
            "url": video.url,
            "description": video.description,
            "published_at": (
                video.published_at.isoformat()
                if video.published_at else None
            ),
            "views_count": (
                snapshot.views_count if snapshot else None
            ),
            "likes_count": (
                snapshot.likes_count if snapshot else None
            ),
            "comments_count": (
                snapshot.comments_count if snapshot else None
            ),
            "shares_count": (
                snapshot.shares_count if snapshot else None
            ),
            "collected_at": (
                snapshot.collected_at.isoformat() + "Z"
                if snapshot else None
            )
        })

    return {
        "club_id": club.id,
        "club_name": club.name,
        "page": page,
        "page_size": page_size,
        "total": total,
        "summary": {
            "videos": total,
            "videos_with_views": videos_with_views,
            "views": summary[2],
            "likes": summary[3],
            "comments": summary[4],
            "shares": summary[5],
            "average_views": (
                round(summary[2] / videos_with_views, 2)
                if summary[2] is not None and videos_with_views
                else None
            )
        },
        "items": items
    }


@app.get("/api/videos/{video_id}/history")
def get_video_history(
    video_id: int,
    db: Session = Depends(get_db)
):
    video = db.get(Video, video_id)

    if video is None:
        raise HTTPException(
            status_code=404,
            detail="Nie znaleziono filmu"
        )

    club = db.get(Club, video.club_id)

    snapshots = db.scalars(
        select(VideoSnapshot)
        .where(VideoSnapshot.video_id == video_id)
        .order_by(
            VideoSnapshot.collected_at.asc(),
            VideoSnapshot.id.asc()
        )
    ).all()

    history = [
        {
            "id": snapshot.id,
            "views_count": snapshot.views_count,
            "likes_count": snapshot.likes_count,
            "comments_count": snapshot.comments_count,
            "shares_count": snapshot.shares_count,
            "collected_at": (
                snapshot.collected_at.isoformat() + "Z"
            )
        }
        for snapshot in snapshots
    ]

    latest = history[-1] if history else None

    # Obliczamy różnicę wyświetleń na podstawie
    # pierwszego i ostatniego odczytu z licznikiem.
    views_measurements = [
        point
        for point in history
        if point["views_count"] is not None
    ]

    views_growth = None

    if len(views_measurements) >= 2:
        views_growth = (
            views_measurements[-1]["views_count"]
            - views_measurements[0]["views_count"]
        )

    return {
        "video": {
            "id": video.id,
            "club_id": video.club_id,
            "club_name": club.name if club else None,
            "tiktok_video_id": video.tiktok_video_id,
            "url": video.url,
            "description": video.description,
            "published_at": (
                video.published_at.isoformat() + "Z"
                if video.published_at else None
            )
        },
        "latest": latest,
        "views_growth": views_growth,
        "measurements_count": len(history),
        "history": history
    }
