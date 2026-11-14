"""FSI 0.7.2: Engagement Analytics dla filmów TikTok."""

from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Club, Video, VideoSnapshot

router = APIRouter(prefix="/api", tags=["Engagement Analytics"])
MIN_RANKING_VIEWS = 1000


def get_engagement_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/clubs/{club_id}/engagement")
def get_club_engagement(
    club_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_engagement_db),
):
    club = db.get(Club, club_id)
    if club is None:
        raise HTTPException(status_code=404, detail="Nie znaleziono klubu")

    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=422,
            detail="Data początkowa jest późniejsza niż końcowa",
        )

    # Jeden, najnowszy snapshot na film; ID rozstrzyga remisy czasu.
    latest_snapshot_id = (
        select(VideoSnapshot.id)
        .where(VideoSnapshot.video_id == Video.id)
        .order_by(
            VideoSnapshot.collected_at.desc(),
            VideoSnapshot.id.desc(),
        )
        .limit(1)
        .correlate(Video)
        .scalar_subquery()
    )

    filters = [Video.club_id == club_id]
    if start_date:
        filters.append(
            Video.published_at >= datetime.combine(start_date, time.min)
        )
    if end_date:
        filters.append(
            Video.published_at < datetime.combine(
                end_date + timedelta(days=1), time.min
            )
        )

    rows = db.execute(
        select(Video, VideoSnapshot)
        .select_from(Video)
        .outerjoin(VideoSnapshot, VideoSnapshot.id == latest_snapshot_id)
        .where(*filters)
    ).all()

    complete = []
    excluded = 0
    included_views = 0
    included_interactions = 0

    for video, snapshot in rows:
        if snapshot is None:
            excluded += 1
            continue

        views = snapshot.views_count
        likes = snapshot.likes_count
        comments = snapshot.comments_count
        shares = snapshot.shares_count

        # Brak danych != zero. Z zerowym licznikiem wyświetleń nie
        # można obliczyć procentowego współczynnika zaangażowania.
        if any(value is None for value in (views, likes, comments, shares)):
            excluded += 1
            continue

        if views <= 0 or any(value < 0 for value in (likes, comments, shares)):
            excluded += 1
            continue

        interactions = likes + comments + shares
        engagement_rate = interactions / views * 100

        included_views += views
        included_interactions += interactions

        complete.append({
            "video_id": video.id,
            "tiktok_video_id": video.tiktok_video_id,
            "url": video.url,
            "description": video.description,
            "published_at": (
                video.published_at.isoformat() + "Z"
                if video.published_at else None
            ),
            "collected_at": snapshot.collected_at.isoformat() + "Z",
            "views": views,
            "likes": likes,
            "comments": comments,
            "shares": shares,
            "interactions": interactions,
            "engagement_rate": round(engagement_rate, 2),
            "_raw_rate": engagement_rate,
        })

    ranked = [
        {key: value for key, value in item.items() if key != "_raw_rate"}
        for item in sorted(
            (item for item in complete if item["views"] >= MIN_RANKING_VIEWS),
            key=lambda item: (item["_raw_rate"], item["views"]),
            reverse=True,
        )[:10]
    ]

    return {
        "club_id": club.id,
        "club_name": club.name,
        "filters": {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        },
        "summary": {
            "videos_total": len(rows),
            "videos_complete": len(complete),
            "videos_excluded": excluded,
            "included_views": included_views,
            "included_interactions": included_interactions,
            "weighted_engagement_rate": (
                round(included_interactions / included_views * 100, 2)
                if included_views > 0 else None
            ),
            "average_engagement_rate": (
                round(
                    sum(item["_raw_rate"] for item in complete)
                    / len(complete),
                    2,
                )
                if complete else None
            ),
        },
        "minimum_views_for_ranking": MIN_RANKING_VIEWS,
        "top_videos": ranked,
    }
