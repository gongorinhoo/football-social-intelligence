
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from database import Base, engine, get_db
from models import Club


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