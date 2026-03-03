"""Match and match participant models for PvP."""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.base import Base
from app.db.models.assessment import ProgrammingLanguage
from app.db.models.question import Question


class MatchStatus(str, enum.Enum):
    """Match session status."""
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class Match(Base):
    """
    PvP match session.
    Two players, same question set, server-authoritative timer.
    """
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(
        Enum(MatchStatus, native_enum=False, length=20),
        default=MatchStatus.WAITING,
        nullable=False
    )
    winner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    language = Column(Enum(ProgrammingLanguage), nullable=False)
    time_limit_per_question = Column(Integer, nullable=False, default=300)  # seconds
    server_started_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    participants = relationship("MatchParticipant", back_populates="match", cascade="all, delete-orphan")
    match_questions = relationship("MatchQuestion", back_populates="match", cascade="all, delete-orphan", order_by="MatchQuestion.order")

    def __repr__(self) -> str:
        return f"<Match(id={self.id}, status={self.status}, winner_id={self.winner_id})>"


class MatchParticipant(Base):
    """Links a user to a match; tracks score and disconnect."""
    __tablename__ = "match_participants"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    score = Column(Float, nullable=True, default=0.0)
    left_at = Column(DateTime(timezone=True), nullable=True)

    match = relationship("Match", back_populates="participants")
    user = relationship("User", backref="match_participations")

    def __repr__(self) -> str:
        return f"<MatchParticipant(match_id={self.match_id}, user_id={self.user_id})>"


class MatchQuestion(Base):
    """Junction: match to questions with order."""
    __tablename__ = "match_questions"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    order = Column(Integer, nullable=False, default=0)

    match = relationship("Match", back_populates="match_questions")
    question = relationship("Question", backref="match_questions")

    def __repr__(self) -> str:
        return f"<MatchQuestion(match_id={self.match_id}, question_id={self.question_id}, order={self.order})>"


class MatchSubmission(Base):
    """A player's answer for one question in a match."""
    __tablename__ = "match_submissions"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    answer_type = Column(String(50), nullable=False)  # mcq, logic_trace, coding
    answer_data = Column(Text, nullable=True)
    is_correct = Column(Boolean, nullable=True)
    score = Column(Float, nullable=True, default=0.0)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<MatchSubmission(match_id={self.match_id}, user_id={self.user_id}, question_id={self.question_id})>"
