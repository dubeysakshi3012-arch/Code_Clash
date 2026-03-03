"""Question and related models."""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean, Enum, JSON, Float
from sqlalchemy.orm import relationship
import enum
from app.db.base import Base


class DifficultyTag(str, enum.Enum):
    """Question difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(str, enum.Enum):
    """Question types for assessment sections."""
    MCQ = "mcq"
    LOGIC_TRACE = "logic_trace"
    CODING = "coding"


class AssessmentSection(str, enum.Enum):
    """Assessment sections."""
    A = "A"  # MCQs
    B = "B"  # Logic & Trace
    C = "C"  # Coding


class ProgrammingLanguage(str, enum.Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVA = "java"
    CPP = "cpp"


class Question(Base):
    """
    Question model representing a concept-based question.
    Questions are dynamically generated based on concepts and templates.
    Extended for assessment module with question types and sections.
    """
    
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    concept_name = Column(String(255), nullable=False, index=True)
    difficulty_tag = Column(Enum(DifficultyTag), nullable=False, index=True)
    logic_description = Column(Text, nullable=False)
    time_limit = Column(Integer, nullable=False, default=30)  # seconds
    memory_limit = Column(Integer, nullable=False, default=256)  # MB
    
    # Assessment module fields
    # Use native_enum=False to store as VARCHAR and use enum values directly
    # This prevents SQLAlchemy from trying to convert database values back to enum members incorrectly
    question_type = Column(
        Enum(QuestionType, native_enum=False, length=50),
        nullable=True,
        index=True
    )
    section = Column(
        Enum(AssessmentSection, native_enum=False, length=10),
        nullable=True,
        index=True
    )
    points = Column(Float, nullable=True, default=0.0)  # Points for this question
    options = Column(JSON, nullable=True)  # For MCQ: {"A": "...", "B": "...", ...}
    correct_answer = Column(Text, nullable=True)  # For MCQ and Logic: correct answer
    # For coding: function name(s) the judge should try when running code (from AI template)
    solution_function_names = Column(JSON, nullable=True)  # e.g. ["sum_numbers", "add"]

    # Relationships
    templates = relationship("QuestionTemplate", back_populates="question", cascade="all, delete-orphan")
    test_cases = relationship("TestCase", back_populates="question", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Question(id={self.id}, concept={self.concept_name}, type={self.question_type}, section={self.section})>"


class QuestionTemplate(Base):
    """
    Language-specific template for a question.
    Contains the problem statement, starter code, and language-specific details.
    """
    
    __tablename__ = "question_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    language = Column(Enum(ProgrammingLanguage), nullable=False)
    problem_statement = Column(Text, nullable=False)
    starter_code = Column(Text, nullable=True)
    solution_template = Column(Text, nullable=True)
    
    # Relationships
    question = relationship("Question", back_populates="templates")
    
    def __repr__(self) -> str:
        return f"<QuestionTemplate(id={self.id}, question_id={self.question_id}, language={self.language})>"


class TestCase(Base):
    """
    Test case model for question validation.
    Can be visible (shown to user) or hidden (for evaluation).
    """
    
    __tablename__ = "test_cases"
    
    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    input_data = Column(Text, nullable=False)
    expected_output = Column(Text, nullable=False)
    is_hidden = Column(Boolean, default=False, nullable=False)
    order = Column(Integer, nullable=False, default=0)
    
    # Relationships
    question = relationship("Question", back_populates="test_cases")
    
    def __repr__(self) -> str:
        return f"<TestCase(id={self.id}, question_id={self.question_id}, hidden={self.is_hidden})>"
