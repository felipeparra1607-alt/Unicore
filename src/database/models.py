from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.connection import Base


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
    )
    academic_year: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    professors: Mapped[list["Professor"]] = relationship(
        back_populates="subject",
        cascade="all, delete-orphan",
    )

    documents: Mapped[list["Document"]] = relationship(
        back_populates="subject",
    )

    classes: Mapped[list["ClassSession"]] = relationship(
        back_populates="subject",
        cascade="all, delete-orphan",
    )

    projects: Mapped[list["Project"]] = relationship(
        back_populates="subject",
    )


class Professor(Base):
    __tablename__ = "professors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
    )
    public_profile_url: Mapped[str | None] = mapped_column(
        String(500)
    )
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    subject: Mapped["Subject"] = relationship(
        back_populates="professors",
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )
    file_path: Mapped[str] = mapped_column(
        String(1000),
        unique=True,
        nullable=False,
    )
    file_type: Mapped[str | None] = mapped_column(String(50))
    document_type: Mapped[str | None] = mapped_column(String(100))
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id"),
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
    )
    extracted_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    subject: Mapped["Subject | None"] = relationship(
        back_populates="documents",
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_document_chunk_index",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chunk_index: Mapped[int] = mapped_column(nullable=False)

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    char_start: Mapped[int] = mapped_column(nullable=False)
    char_end: Mapped[int] = mapped_column(nullable=False)

    source_label: Mapped[str | None] = mapped_column(
        String(100)
    )

    chunking_strategy: Mapped[str] = mapped_column(
        String(50),
        default="hybrid_semantic",
        nullable=False,
    )

    embedding_model: Mapped[str | None] = mapped_column(
        String(250)
    )

    embedding_json: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    document: Mapped["Document"] = relationship(
        back_populates="chunks",
    )


class ClassSession(Base):
    __tablename__ = "class_sessions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    class_date: Mapped[date | None] = mapped_column(
        Date,
    )

    start_time: Mapped[str | None] = mapped_column(
        String(5),
    )

    end_time: Mapped[str | None] = mapped_column(
        String(5),
    )

    session_type: Mapped[str | None] = mapped_column(
        String(50),
    )

    location: Mapped[str | None] = mapped_column(
        String(250),
    )

    attended: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
    )

    professor_id: Mapped[int | None] = mapped_column(
        ForeignKey("professors.id"),
    )

    source_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id"),
    )

    topics: Mapped[str | None] = mapped_column(
        Text,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
    )

    transcript: Mapped[str | None] = mapped_column(
        Text,
    )

    summary: Mapped[str | None] = mapped_column(
        Text,
    )

    doubts: Mapped[str | None] = mapped_column(
        Text,
    )

    tasks: Mapped[str | None] = mapped_column(
        Text,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    subject: Mapped["Subject"] = relationship(
        back_populates="classes",
    )
    
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id"),
    )
    personal_contribution: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    subject: Mapped["Subject | None"] = relationship(
        back_populates="projects",
    )