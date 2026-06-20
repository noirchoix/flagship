# api/db.py

import os
from datetime import datetime
from sqlalchemy import (
    create_engine, String, Text, DateTime, ForeignKey, Integer
)
from sqlalchemy.orm import (
    declarative_base, sessionmaker, scoped_session,
    relationship, Mapped, mapped_column
)

DATABASE_URL = os.getenv("RESEARCH_DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///./data/research/research_app.db"))
if DATABASE_URL.startswith("sqlite") and ":///" in DATABASE_URL:
    from pathlib import Path as _Path
    _db_file = DATABASE_URL.split(":///", 1)[1]
    if _db_file and _db_file != ":memory:":
        _Path(_db_file).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)

SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)

Base = declarative_base()


# ============================================================
# MODELS — FIXED WITH Mapped[] and mapped_column()
# ============================================================

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    jobs: Mapped[list["Job"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan"
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(Integer, ForeignKey("documents.id"), nullable=False)

    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    output_format: Mapped[str] = mapped_column(String(20), nullable=False)

    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    result_text: Mapped[str] = mapped_column(Text, nullable=False)

    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    document: Mapped[Document] = relationship(back_populates="jobs")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
