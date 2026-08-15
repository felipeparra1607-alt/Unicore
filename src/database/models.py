from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    Float,
    Integer,
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
    academic_language: Mapped[str] = mapped_column(
        String(30),
        default="Spanish",
        nullable=False,
    )
    academic_language_configured: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
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
    material_type: Mapped[str] = mapped_column(
        String(40), default="other", nullable=False, index=True
    )
    curriculum_unit_id: Mapped[int | None] = mapped_column(
        ForeignKey("curriculum_items.id", ondelete="SET NULL"), index=True
    )
    academic_year: Mapped[str | None] = mapped_column(String(20))
    semester: Mapped[str | None] = mapped_column(String(40))
    professor_id: Mapped[int | None] = mapped_column(
        ForeignKey("professors.id")
    )
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id"),
    )
    content_hash: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
    )
    extracted_text: Mapped[str | None] = mapped_column(Text)
    curriculum_processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    processing_status: Mapped[str] = mapped_column(
        String(30), default="ready", nullable=False
    )
    processing_stage: Mapped[str | None] = mapped_column(String(100))
    processing_error: Mapped[str | None] = mapped_column(Text)
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


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(
        String(80),
        primary_key=True,
    )
    title: Mapped[str] = mapped_column(
        String(180),
        nullable=False,
    )
    context_type: Mapped[str] = mapped_column(
        String(30),
        default="general",
        nullable=False,
    )
    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id"),
        index=True,
    )
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id"),
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(Text)
    summarized_message_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
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

    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ConversationMessage.id",
    )


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    sources_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    conversation: Mapped["Conversation"] = relationship(
        back_populates="messages",
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
class StudyAttempt(Base):
    __tablename__ = "study_attempts"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
    )

    topic: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    study_mode: Mapped[str] = mapped_column(
        String(50),
        default="quiz",
        nullable=False,
    )

    difficulty: Mapped[str | None] = mapped_column(
        String(50),
    )

    questions_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    answers_json: Mapped[str | None] = mapped_column(
        Text,
    )

    results_json: Mapped[str | None] = mapped_column(
        Text,
    )

    total_questions: Mapped[int] = mapped_column(
        nullable=False,
    )

    correct_answers: Mapped[int | None] = mapped_column()

    score_percentage: Mapped[float | None] = mapped_column()

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
    )


class StudyAnswer(Base):
    __tablename__ = "study_answers"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    attempt_id: Mapped[int] = mapped_column(
        ForeignKey("study_attempts.id"),
        nullable=False,
    )

    question_index: Mapped[int] = mapped_column(
        nullable=False,
    )

    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    selected_index: Mapped[int] = mapped_column(
        nullable=False,
    )

    correct_index: Mapped[int] = mapped_column(
        nullable=False,
    )

    is_correct: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
    )

    sources_json: Mapped[str | None] = mapped_column(
        Text,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )   
class ReviewItem(Base):
    __tablename__ = "review_items"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
    )

    source_attempt_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_attempts.id"),
    )

    source_answer_id: Mapped[int | None] = mapped_column(
        ForeignKey("study_answers.id"),
    )

    topic: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    question: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    correct_answer: Mapped[str | None] = mapped_column(
        Text,
    )

    explanation: Mapped[str | None] = mapped_column(
        Text,
    )

    sources_json: Mapped[str | None] = mapped_column(
        Text,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="learning",
        nullable=False,
    )

    priority: Mapped[int] = mapped_column(
        default=3,
        nullable=False,
    )

    repetition_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    correct_streak: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    incorrect_count: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
    )

    interval_days: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
    )

    ease_factor: Mapped[float] = mapped_column(
        default=2.5,
        nullable=False,
    )

    leitner_box: Mapped[int] = mapped_column(
        default=1,
        nullable=False,
    )

    cognitive_level: Mapped[str] = mapped_column(
        String(30),
        default="mixed",
        nullable=False,
    )

    concept_name: Mapped[str | None] = mapped_column(
        String(250),
    )

    last_rating: Mapped[str | None] = mapped_column(
        String(30),
    )

    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
    )

    next_review_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
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
class StudySession(Base):
    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
    )

    session_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
    )

    duration_minutes: Mapped[int] = mapped_column(
        nullable=False,
    )

    activity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    topic: Mapped[str | None] = mapped_column(
        String(250),
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
    )

    planned_minutes: Mapped[int | None] = mapped_column()

    completed_plan: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    focus_rating: Mapped[int | None] = mapped_column()

    difficulty_rating: Mapped[int | None] = mapped_column()

    satisfaction_rating: Mapped[int | None] = mapped_column()

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
class AcademicTask(Base):
    __tablename__ = "academic_tasks"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id"),
    )

    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    task_type: Mapped[str] = mapped_column(
        String(50),
        default="other",
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )

    priority: Mapped[int] = mapped_column(
        default=3,
        nullable=False,
    )

    due_date: Mapped[date | None] = mapped_column(
        Date,
    )

    estimated_minutes: Mapped[int | None] = mapped_column()

    spent_minutes: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    progress_percentage: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
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
class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    assessment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    assessment_date: Mapped[date | None] = mapped_column(
        Date,
    )

    weight_percentage: Mapped[float] = mapped_column(
        nullable=False,
    )

    maximum_grade: Mapped[float] = mapped_column(
        default=10.0,
        nullable=False,
    )

    obtained_grade: Mapped[float | None] = mapped_column()

    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    professor_feedback: Mapped[str | None] = mapped_column(
        Text,
    )

    notes: Mapped[str | None] = mapped_column(
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


class GradeGoal(Base):
    __tablename__ = "grade_goals"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
    )

    target_grade: Mapped[float] = mapped_column(
        nullable=False,
    )

    maximum_grade: Mapped[float] = mapped_column(
        default=10.0,
        nullable=False,
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
class ProfessorPreference(Base):
    __tablename__ = "professor_preferences"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    professor_id: Mapped[int] = mapped_column(
        ForeignKey("professors.id"),
        nullable=False,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    preference: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    importance: Mapped[int] = mapped_column(
        default=3,
        nullable=False,
    )

    source_type: Mapped[str | None] = mapped_column(
        String(50),
    )

    source_reference: Mapped[str | None] = mapped_column(
        Text,
    )

    confidence: Mapped[int] = mapped_column(
        default=3,
        nullable=False,
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


class RubricCriterion(Base):
    __tablename__ = "rubric_criteria"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
    )

    professor_id: Mapped[int | None] = mapped_column(
        ForeignKey("professors.id"),
    )

    assessment_id: Mapped[int | None] = mapped_column(
        ForeignKey("assessments.id"),
    )

    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    weight_percentage: Mapped[float | None] = mapped_column()

    maximum_points: Mapped[float | None] = mapped_column()

    notes: Mapped[str | None] = mapped_column(
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
class GamificationEvent(Base):
    __tablename__ = "gamification_events"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id"),
    )

    event_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    source_key: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    xp_points: Mapped[int] = mapped_column(
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class AchievementUnlock(Base):
    __tablename__ = "achievement_unlocks"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    achievement_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id"),
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )


class DailyMission(Base):
    __tablename__ = "daily_missions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    mission_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    subject_id: Mapped[int | None] = mapped_column(
        ForeignKey("subjects.id"),
    )

    mission_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    source_key: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    target_value: Mapped[int] = mapped_column(
        nullable=False,
    )

    current_value: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    reward_xp: Mapped[int] = mapped_column(
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="active",
        nullable=False,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime,
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
class BossBattle(Base):
    __tablename__ = "boss_battles"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
    )

    assessment_id: Mapped[int] = mapped_column(
        ForeignKey("assessments.id"),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="preparing",
        nullable=False,
    )

    target_score_percentage: Mapped[float] = mapped_column(
        default=80.0,
        nullable=False,
    )

    readiness_percentage: Mapped[float] = mapped_column(
        default=0.0,
        nullable=False,
    )

    weak_topics_json: Mapped[str | None] = mapped_column(
        Text,
    )

    recommended_actions_json: Mapped[str | None] = mapped_column(
        Text,
    )

    reward_xp: Mapped[int] = mapped_column(
        default=150,
        nullable=False,
    )

    best_score_percentage: Mapped[float | None] = mapped_column()

    attempt_count: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    defeated_at: Mapped[datetime | None] = mapped_column(
        DateTime,
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
class KnowledgeConcept(Base):
    __tablename__ = "knowledge_concepts"

    __table_args__ = (
        UniqueConstraint(
            "subject_id",
            "normalized_name",
            name="uq_knowledge_concept_subject_name",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    normalized_name: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    global_concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("global_concepts.id"),
        index=True,
    )

    mastery_percentage: Mapped[float | None] = mapped_column(
        Float,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="unassessed",
        nullable=False,
    )

    evidence_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    assessed_evidence_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    exposure_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    last_evidence_at: Mapped[datetime | None] = mapped_column(
        DateTime,
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


class KnowledgeEvidence(Base):
    __tablename__ = "knowledge_evidence"

    __table_args__ = (
        UniqueConstraint(
            "concept_id",
            "source_type",
            "source_id",
            name="uq_knowledge_evidence_source",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    concept_id: Mapped[int] = mapped_column(
        ForeignKey(
            "knowledge_concepts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    subject_id: Mapped[int] = mapped_column(
        ForeignKey("subjects.id"),
        nullable=False,
        index=True,
    )

    source_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    source_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    evidence_score: Mapped[float | None] = mapped_column(
        Float,
    )

    weight: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )

    exposure_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    observed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
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


class FlashcardDraft(Base):
    __tablename__ = "flashcard_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    topic: Mapped[str] = mapped_column(String(250), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str | None] = mapped_column(Text)
    cognitive_level: Mapped[str] = mapped_column(String(30), default="mixed", nullable=False)
    answer_mode: Mapped[str] = mapped_column(String(30), default="mental", nullable=False)
    probable_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    duplicate_review_item_id: Mapped[int | None] = mapped_column(ForeignKey("review_items.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    rejection_reason: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)


class ExplanationCache(Base):
    __tablename__ = "explanation_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, index=True)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"), index=True)
    curriculum_item_id: Mapped[int | None] = mapped_column(index=True)
    topic_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    difficulty: Mapped[str] = mapped_column(String(50), nullable=False)
    material_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TokenUsage(Base):
    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    feature: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("conversations.id"), index=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    provider: Mapped[str | None] = mapped_column(String(60))
    model: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class WrittenEvaluation(Base):
    __tablename__ = "written_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_item_id: Mapped[int] = mapped_column(ForeignKey("review_items.id"), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, index=True)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    overall_score: Mapped[float | None] = mapped_column(Float)
    dimensions_json: Mapped[str] = mapped_column(Text, nullable=False)
    errors_json: Mapped[str] = mapped_column(Text, nullable=False)
    improvements_json: Mapped[str] = mapped_column(Text, nullable=False)
    example_improvement: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(String(60))
    model: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class StudentModelEvidence(Base):
    __tablename__ = "student_model_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int | None] = mapped_column(ForeignKey("subjects.id"), index=True)
    dimension: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class ProfessorAssignment(Base):
    __tablename__ = "professor_assignments"
    __table_args__ = (UniqueConstraint("professor_id", "subject_id", name="uq_professor_subject"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    professor_id: Mapped[int] = mapped_column(ForeignKey("professors.id"), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class KnowledgeConnection(Base):
    __tablename__ = "knowledge_connections"
    __table_args__ = (
        UniqueConstraint("source_concept_id", "target_concept_id", name="uq_knowledge_connection"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_concept_id: Mapped[int] = mapped_column(ForeignKey("knowledge_concepts.id"), nullable=False)
    target_concept_id: Mapped[int] = mapped_column(ForeignKey("knowledge_concepts.id"), nullable=False)
    relationship: Mapped[str] = mapped_column(String(120), default="related", nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    evidence_reference: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class GlobalConcept(Base):
    __tablename__ = "global_concepts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(250), unique=True, nullable=False, index=True)
    aliases_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="automatic", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class CurriculumItem(Base):
    __tablename__ = "curriculum_items"
    __table_args__ = (
        UniqueConstraint("subject_id", "item_type", "normalized_name", name="uq_curriculum_subject_type_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False, index=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("curriculum_items.id", ondelete="SET NULL"), index=True)
    item_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(250), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(250), nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(30), default="automatic", nullable=False)
    manually_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class CurriculumDocumentReference(Base):
    __tablename__ = "curriculum_document_references"
    __table_args__ = (
        UniqueConstraint("curriculum_item_id", "document_id", name="uq_curriculum_document_reference"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_item_id: Mapped[int] = mapped_column(ForeignKey("curriculum_items.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    source_label: Mapped[str | None] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CurriculumChunkReference(Base):
    __tablename__ = "curriculum_chunk_references"
    __table_args__ = (
        UniqueConstraint("curriculum_item_id", "chunk_id", name="uq_curriculum_chunk_reference"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_item_id: Mapped[int] = mapped_column(ForeignKey("curriculum_items.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class CurriculumConceptLink(Base):
    __tablename__ = "curriculum_concept_links"
    __table_args__ = (
        UniqueConstraint("curriculum_item_id", "knowledge_concept_id", name="uq_curriculum_concept_link"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    curriculum_item_id: Mapped[int] = mapped_column(ForeignKey("curriculum_items.id", ondelete="CASCADE"), nullable=False, index=True)
    knowledge_concept_id: Mapped[int] = mapped_column(ForeignKey("knowledge_concepts.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship: Mapped[str] = mapped_column(String(40), default="represents", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
