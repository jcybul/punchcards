# db.py
import os
import urllib.parse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from dotenv import load_dotenv

load_dotenv() 

def get_database_url() -> str:
    """
    Build a proper SQLAlchemy connection string for Supabase.
    Requires these env vars in your .env:
      DB_USER=postgres.<project-ref>
      DB_PASS=your-password
      DB_HOST=db.<project-ref>.supabase.co
      DB_PORT=5432
      DB_NAME=postgres
    """
    user = os.getenv("user")
    password = os.getenv("password")
    host = os.getenv("host")
    port = os.getenv("port", "5432")
    name = os.getenv("dbname", "postgres")

    if not all([user, password, host]):
        raise RuntimeError("Missing required DB env vars (DB_USER, DB_PASS, DB_HOST)")

    # URL encode the password (handles @, :, /, etc.)
    password = urllib.parse.quote_plus(password)

    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{name}?sslmode=require"


# Engine & Session setup
DATABASE_URL = get_database_url()
engine = create_engine(DATABASE_URL, future=True)

SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
)

# Dependency for Flask endpoints
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
