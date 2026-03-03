"""Assessment and result models."""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, DateTime, Enum, JSON, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.base import Base
from app.db.models.question import AssessmentSection as SectionEnum


class AssessmentStatus(str, enum.Enum):
    """Assessment session status."""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    SKIPPED = "skipped"


class ProgrammingLanguage(str, enum.Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVA = "java"
    CPP = "cpp"


class Assessment(Base):
    """
    Assessment session model.
    Represents a user's assessment attempt with selected language.
    Extended for section-based assessment flow.
    """
    
    __tablename__ = "assessments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    language = Column(Enum(ProgrammingLanguage), nullable=False)
    status = Column(
        Enum(AssessmentStatus, native_enum=False, length=20),
        default=AssessmentStatus.IN_PROGRESS,
        nullable=False,
    )
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Section tracking
    current_section = Column(
        Enum(SectionEnum, native_enum=False, length=10),
        nullable=True,
        default=SectionEnum.A
    )
    total_score = Column(Float, nullable=True, default=0.0)
    section_a_score = Column(Float, nullable=True, default=0.0)
    section_b_score = Column(Float, nullable=True, default=0.0)
    section_c_score = Column(Float, nullable=True, default=0.0)
    
    # Anti-cheating fields
    violation_count = Column(Integer, default=0, nullable=False)
    auto_submitted = Column(Boolean, default=False, nullable=False)
    server_start_time = Column(DateTime(timezone=True), nullable=True)  # For server-side timer validation
    
    # Relationships
    user = relationship("User", backref="assessments")
    results = relationship("AssessmentResult", back_populates="assessment", cascade="all, delete-orphan")
    sections = relationship("AssessmentSection", back_populates="assessment", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Assessment(id={self.id}, user_id={self.user_id}, language={self.language}, status={self.status}, section={self.current_section})>"


class AssessmentSection(Base):
    """
    Assessment section tracking model.
    Tracks progress and timing for each section (A, B, C).
    """
    
    __tablename__ = "assessment_sections"
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    section = Column(
        Enum(SectionEnum, native_enum=False, length=10),
        nullable=False
    )
    started_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    score = Column(Float, nullable=True, default=0.0)
    is_completed = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    assessment = relationship("Assessment", back_populates="sections")
    
    def __repr__(self) -> str:
        return f"<AssessmentSection(id={self.id}, assessment_id={self.assessment_id}, section={self.section}, completed={self.is_completed})>"


class AssessmentQuestion(Base):
    """
    Junction table linking assessments to questions.
    Tracks which questions were assigned to an assessment.
    """
    
    __tablename__ = "assessment_questions"
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    order = Column(Integer, nullable=False, default=0)
    
    # Relationships
    assessment = relationship("Assessment", backref="assessment_questions")
    question = relationship("Question", backref="assessment_questions")
    
    def __repr__(self) -> str:
        return f"<AssessmentQuestion(assessment_id={self.assessment_id}, question_id={self.question_id})>"


class AssessmentResult(Base):
    """
    Assessment result model.
    Stores user's answers and evaluation results for each question.
    Extended for comprehensive scoring and section tracking.
    """
    
    __tablename__ = "assessment_results"
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    
    # Answer data (can be MCQ, logic, or code submission)
    answer_type = Column(String(50), nullable=False)  # "mcq", "logic_trace", or "coding"
    answer_data = Column(Text, nullable=True)  # JSON string or code
    mcq_answer = Column(String(10), nullable=True)  # For MCQ questions
    logic_answer = Column(Text, nullable=True)  # For logic/trace questions
    
    # Section tracking
    section = Column(
        Enum(SectionEnum, native_enum=False, length=10),
        nullable=True,
        index=True
    )
    
    # Evaluation results
    is_correct = Column(Boolean, nullable=True)  # None if not evaluated yet
    execution_result = Column(JSON, nullable=True)  # Judge execution results
    execution_metadata = Column(JSON, nullable=True)  # Runtime, memory, attempts, etc.
    verdict = Column(String(50), nullable=True)  # Verdict: ACCEPTED, WRONG_ANSWER, TLE, etc.
    complexity_detected = Column(String(20), nullable=True)  # Detected complexity: O(N), O(N²), etc.
    stress_test_results = Column(JSON, nullable=True)  # Stress test results for complexity detection
    score = Column(Float, nullable=True, default=0.0)
    partial_score = Column(Float, nullable=True, default=0.0)  # For partial credit
    attempts_count = Column(Integer, nullable=False, default=1)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    assessment = relationship("Assessment", back_populates="results")
    question = relationship("Question", backref="assessment_results")
    
    def __repr__(self) -> str:
        return f"<AssessmentResult(id={self.id}, assessment_id={self.assessment_id}, section={self.section}, is_correct={self.is_correct}, score={self.score})>"
