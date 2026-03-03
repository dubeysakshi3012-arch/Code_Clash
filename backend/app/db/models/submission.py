"""Submission model for Online Judge queue system."""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Enum, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.base import Base
from app.db.models.assessment import ProgrammingLanguage


class SubmissionStatus(str, enum.Enum):
    """Submission processing status."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Verdict(str, enum.Enum):
    """Submission verdict types."""
    ACCEPTED = "ACCEPTED"
    WRONG_ANSWER = "WRONG_ANSWER"
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
    MEMORY_LIMIT_EXCEEDED = "MEMORY_LIMIT_EXCEEDED"
    RUNTIME_ERROR = "RUNTIME_ERROR"
    COMPILATION_ERROR = "COMPILATION_ERROR"
    CORRECT_BUT_SLOW = "CORRECT_BUT_SLOW"


class Submission(Base):
    """
    Submission model for Online Judge.
    
    Represents a user's code submission that is queued for evaluation.
    Separate from AssessmentResult to support generic judge functionality.
    """
    
    __tablename__ = "submissions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    problem_id = Column(Integer, ForeignKey("questions.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Submission details
    language = Column(Enum(ProgrammingLanguage), nullable=False)
    source_code = Column(Text, nullable=False)
    
    # Processing status
    status = Column(Enum(SubmissionStatus), default=SubmissionStatus.QUEUED, nullable=False, index=True)
    
    # Results
    verdict = Column(String(50), nullable=True, index=True)
    execution_time = Column(Float, nullable=True)  # seconds
    memory_usage = Column(Integer, nullable=True)  # MB
    test_cases_passed = Column(Integer, nullable=True, default=0)
    total_test_cases = Column(Integer, nullable=True, default=0)
    execution_result = Column(JSON, nullable=True)  # Full judge execution results
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user = relationship("User", backref="submissions")
    problem = relationship("Question", backref="submissions")
    
    def __repr__(self) -> str:
        return f"<Submission(id={self.id}, user_id={self.user_id}, problem_id={self.problem_id}, status={self.status}, verdict={self.verdict})>"
