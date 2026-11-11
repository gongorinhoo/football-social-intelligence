
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


# Ścieżka do folderu backend
BASE_DIR = Path(__file__).resolve().parent

# Wczytanie konfiguracji
load_dotenv(BASE_DIR / ".env")


# Dane połączenia z MySQL
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME")


# Sprawdzenie konfiguracji
if not all([DB_USER, DB_PASSWORD, DB_NAME]):
    raise RuntimeError(
        "Brakuje konfiguracji bazy danych w pliku .env"
    )


# Konfiguracja połączenia
DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    query={"charset": "utf8mb4"}
)


# Silnik bazy danych
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)


# Fabryka sesji
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False
)


# Klasa bazowa modeli SQLAlchemy
class Base(DeclarativeBase):
    pass


# Sesja dla endpointów FastAPI
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
