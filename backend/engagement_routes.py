from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from database import SessionLocal
from models import Club, Video, VideoSnapshot

router = APIRouter(prefix="/api/rankings", tags=["rankings"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/clubs")
def get_club_rankings(
    start_date: date | None = None,
    end_date: date | None = None,
    sort_by: Literal["views", "avg_views", "er"] = "avg_views",
    min_videos: int = Query(1, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="Nieprawidłowy zakres dat")

    # Daty ograniczają czas PUBLIKACJI, a nie czas zdobycia wyświetleń.
    video_join = [Video.club_id == Club.id]
    if start_date:
        video_join.append(Video.published_at >= datetime.combine(start_date, time.min))
    if end_date:
        video_join.append(Video.published_at < datetime.combine(end_date + timedelta(days=1), time.min))

    # Dla każdego filmu bierzemy wyłącznie najnowszy snapshot.
    latest_snapshot_id = (
        select(VideoSnapshot.id)
        .where(VideoSnapshot.video_id == Video.id)
        .order_by(VideoSnapshot.collected_at.desc(), VideoSnapshot.id.desc())
        .limit(1)
        .correlate(Video)
        .scalar_subquery()
    )

    # ER liczymy tylko wtedy, gdy wszystkie metryki są dostępne.
    complete = and_(
        VideoSnapshot.views_count.is_not(None),
        VideoSnapshot.views_count > 0,
        VideoSnapshot.likes_count.is_not(None),
        VideoSnapshot.comments_count.is_not(None),
        VideoSnapshot.shares_count.is_not(None),
    )

    stmt = (
        select(
            Club.id.label("club_id"),
            Club.name.label("club_name"),
            Club.tiktok_handle.label("tiktok_handle"),
            func.count(Video.id).label("videos_total"),
            func.count(VideoSnapshot.views_count).label("videos_with_views"),
            func.sum(VideoSnapshot.views_count).label("total_views"),
            func.sum(case((complete, 1), else_=0)).label("videos_with_complete_er"),
            func.sum(case((complete, VideoSnapshot.views_count), else_=0)).label("er_views"),
            func.sum(
                case(
                    (
                        complete,
                        VideoSnapshot.likes_count
                        + VideoSnapshot.comments_count
                        + VideoSnapshot.shares_count,
                    ),
                    else_=0,
                )
            ).label("er_interactions"),
        )
        .select_from(Club)
        .outerjoin(Video, and_(*video_join))
        .outerjoin(VideoSnapshot, VideoSnapshot.id == latest_snapshot_id)
        .where(Club.is_active.is_(True))
        .group_by(Club.id, Club.name, Club.tiktok_handle)
    )

    clubs = []
    for row in db.execute(stmt).mappings():
        videos_total = int(row["videos_total"])
        with_views = int(row["videos_with_views"])
        complete_count = int(row["videos_with_complete_er"] or 0)
        total_views = int(row["total_views"]) if with_views else None
        er_views = int(row["er_views"] or 0)
        er_interactions = int(row["er_interactions"] or 0)
        average_views = round(total_views / with_views, 1) if with_views else None
        er = round(100 * er_interactions / er_views, 2) if er_views > 0 else None

        metric = {"views": total_views, "avg_views": average_views, "er": er}[sort_by]
        eligible_videos = complete_count if sort_by == "er" else with_views
        eligible = eligible_videos >= min_videos and metric is not None

        clubs.append({
            "club_id": row["club_id"],
            "club_name": row["club_name"],
            "tiktok_handle": row["tiktok_handle"],
            "videos_total": videos_total,
            "videos_with_views": with_views,
            "videos_with_complete_er": complete_count,
            "total_views": total_views,
            "average_views": average_views,
            "weighted_er": er,
            "eligible": eligible,
            "rank": None,
            "_metric": metric,
        })

    clubs.sort(key=lambda c: (
        not c["eligible"],
        -(c["_metric"] if c["eligible"] else 0),
        c["club_name"].casefold(),
    ))

    ranked = 0
    for club in clubs:
        if club["eligible"]:
            ranked += 1
            club["rank"] = ranked
        del club["_metric"]

    return {
        "sort_by": sort_by,
        "min_videos": min_videos,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "clubs_total": len(clubs),
        "clubs_ranked": ranked,
        "clubs": clubs,
    }
