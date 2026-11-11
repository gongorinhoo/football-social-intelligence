
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    BigInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utc_now():
    """Aktualny czas UTC bez informacji o strefie dla MySQL DATETIME."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# 1. KLUBY – istniejąca tabela

class Club(Base):
    __tablename__ = "clubs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True
    )

    tiktok_handle: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    league: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False
    )

    # Relacje z nowymi tabelami
    profile_snapshots: Mapped[list["ProfileSnapshot"]] = relationship(
        back_populates="club"
    )

    videos: Mapped[list["Video"]] = relationship(
        back_populates="club"
    )


# 2. HISTORIA STATYSTYK PROFILI

class ProfileSnapshot(Base):
    __tablename__ = "profile_snapshots"

    __table_args__ = (
        Index("ix_profile_club_time", "club_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    club_id: Mapped[int] = mapped_column(
        ForeignKey("clubs.id"),
        nullable=False
    )

    followers_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True
    )

    likes_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False
    )

    club: Mapped["Club"] = relationship(
        back_populates="profile_snapshots"
    )


# 3. FILMY TIKTOK

class Video(Base):
    __tablename__ = "videos"

    __table_args__ = (
        UniqueConstraint(
            "tiktok_video_id",
            name="uq_tiktok_video_id"
        ),
        Index("ix_video_club_published", "club_id", "published_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    club_id: Mapped[int] = mapped_column(
        ForeignKey("clubs.id"),
        nullable=False
    )

    tiktok_video_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    url: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    published_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False
    )

    club: Mapped["Club"] = relationship(
        back_populates="videos"
    )

    snapshots: Mapped[list["VideoSnapshot"]] = relationship(
        back_populates="video"
    )


# 4. HISTORIA STATYSTYK FILMÓW

class VideoSnapshot(Base):
    __tablename__ = "video_snapshots"

    __table_args__ = (
        Index("ix_video_snapshot_time", "video_id", "collected_at"),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id"),
        nullable=False
    )

    views_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True
    )

    likes_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True
    )

    comments_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True
    )

    shares_count: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True
    )

    collected_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=utc_now,
        nullable=False
    )

    video: Mapped["Video"] = relationship(
        back_populates="snapshots"
    )
