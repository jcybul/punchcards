# app/db.py
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

is_cloud_run = os.getenv("K_SERVICE") is not None

if is_cloud_run:
    # Cloud Run: Very aggressive connection management
    engine = create_engine(
        DATABASE_URL,
        pool_size=4,
        max_overflow=0,
        pool_recycle=60,      
        pool_pre_ping=True,
        pool_timeout=15,      
        echo=False
    )
else:
    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        echo=False
    )

# @event.listens_for(engine, "connect")
# def receive_connect(dbapi_conn, connection_record):
#     print(f"DB connection opened: {id(dbapi_conn)}")

# @event.listens_for(engine, "close")
# def receive_close(dbapi_conn, connection_record):
#     print(f"DB connection closed: {id(dbapi_conn)}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
