from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://unpo_admin:secure_password_123@db:5432/unpo_nora_db")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,      # Check connection validity before using it
    pool_recycle=1800,       # Recycle connections after 30 minutes
    pool_size=10,            # Limit connections
    max_overflow=20          # Allow up to 20 connections above the pool size
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
