"""Question-related Pydantic schemas."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.db.models.question import DifficultyTag, ProgrammingLanguage, QuestionType, AssessmentSection


class TestCaseResponse(BaseModel):
    """Schema for test case response (only visible test cases)."""
    id: int
    input_data: str
    expected_output: str
    order: int
    
    class Config:
        from_attributes = True


class QuestionResponse(BaseModel):
    """Schema for question response."""
    id: int
    concept_name: str
    difficulty_tag: DifficultyTag
    logic_description: str
    time_limit: int
    memory_limit: int
    problem_statement: str
    starter_code: Optional[str]
    language: ProgrammingLanguage
    visible_test_cases: List[TestCaseResponse] = Field(default_factory=list)
    
    class Config:
        from_attributes = True


class QuestionListResponse(BaseModel):
    """Schema for list of questions."""
    questions: List[QuestionResponse]
    total: int


class MCQQuestionResponse(BaseModel):
    """Schema for MCQ question response."""
    id: int
    concept_name: str
    logic_description: str
    options: Dict[str, str]
    points: float
    
    class Config:
        from_attributes = True


class LogicQuestionResponse(BaseModel):
    """Schema for Logic & Trace question response."""
    id: int
    concept_name: str
    logic_description: str
    points: float
    
    class Config:
        from_attributes = True


class CodingQuestionResponse(BaseModel):
    """Schema for coding question response."""
    id: int
    concept_name: str
    logic_description: str
    problem_statement: str
    starter_code: Optional[str]
    time_limit: int
    memory_limit: int
    visible_test_cases: List[TestCaseResponse]
    points: float
    
    class Config:
        from_attributes = True


class SectionQuestionsResponse(BaseModel):
    """Schema for section questions response."""
    section: str
    questions: List[Dict[str, Any]]
    total: int
    language: Optional[str] = None