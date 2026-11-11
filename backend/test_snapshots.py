
from datetime import datetime, timezone

from sqlalchemy import select, func

from database import SessionLocal
from models import Club, ProfileSnapshot, Video, VideoSnapshot


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_database():
    db = SessionLocal()

    try:
        # Wybieramy istniejący klub
        club = db.scalar(
            select(Club).where(
                Club.tiktok_handle == "wislakrakowsa"
            )
        )

        if club is None:
            print("Nie znaleziono Wisły Kraków.")
            return

        print(f"TEST KLUBU: {club.name}")

        # Przykładowy pomiar profilu
        profile_snapshot = ProfileSnapshot(
            club_id=club.id,
            followers_count=100000,
            likes_count=500000,
            collected_at=utc_now()
        )
        db.add(profile_snapshot)
        db.flush()

        # Przykładowy film testowy
        video = Video(
            club_id=club.id,
            tiktok_video_id="FSI_TEST_VIDEO_0001",
            url="https://example.com/fsi-test-video",
            description="Test relacji w bazie danych",
            published_at=utc_now()
        )
        db.add(video)
        db.flush()

        # Przykładowy pomiar filmu
        video_snapshot = VideoSnapshot(
            video_id=video.id,
            views_count=25000,
            likes_count=2000,
            comments_count=150,
            shares_count=80,
            collected_at=utc_now()
        )
        db.add(video_snapshot)
        db.flush()

        # Sprawdzenie odczytu z bazy
        saved_snapshot = db.get(
            VideoSnapshot, video_snapshot.id
        )

        saved_profile = db.get(
            ProfileSnapshot, profile_snapshot.id
        )

        assert saved_snapshot is not None
        assert saved_snapshot.views_count == 25000
        assert saved_profile is not None
        assert saved_profile.followers_count == 100000

        print("Poprawnie zapisano i odczytano dane testowe.")
        print(f"Klub: {club.name}")
        print(f"Testowe ID filmu: {video.id}")
        print(f"Wyświetlenia: {saved_snapshot.views_count}")
        print(f"Obserwujący: {saved_profile.followers_count}")

    finally:
        # Wycofujemy dane testowe – nic nie zostaje w bazie
        db.rollback()
        db.close()
        print("Transakcja testowa wycofana.")


if __name__ == "__main__":
    test_database()
