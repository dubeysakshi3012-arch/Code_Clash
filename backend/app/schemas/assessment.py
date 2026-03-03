"""Assessment-related Pydantic schemas."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.db.models.assessment import AssessmentStatus, ProgrammingLanguage
from app.db.models.question import AssessmentSection, QuestionType


class LanguageSelection(BaseModel):
    """Schema for language selection when starting assessment."""
    language: ProgrammingLanguage


class AssessmentSkip(BaseModel):
    """Schema for skipping assessment."""
    selected_language: Optional[ProgrammingLanguage] = Field(None, description="Optional language preference")


class AssessmentSkipResponse(BaseModel):
    """Schema for skip assessment response."""
    status: str = "success"
    elo_rating: int
    message: Optional[str] = None


class AssessmentStart(BaseModel):
    """Schema for starting an assessment."""
    language: ProgrammingLanguage


class AssessmentResponse(BaseModel):
    """Schema for assessment response."""
    id: int
    user_id: int
    language: ProgrammingLanguage
    status: AssessmentStatus
    started_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class AnswerSubmission(BaseModel):
    """Schema for submitting an answer."""
    question_id: int
    answer_type: str = Field(..., description="Type of answer: 'mcq' or 'coding'")
    answer_data: Optional[str] = Field(None, description="Code submission or JSON data")
    mcq_answer: Optional[str] = Field(None, description="MCQ answer option")


class AssessmentResultResponse(BaseModel):
    """Schema for assessment result response."""
    id: int
    assessment_id: int
    question_id: int
    answer_type: str
    is_correct: Optional[bool]
    score: Optional[float]  # Changed from int to float to support decimal scores
    submitted_at: datetime
    
    class Config:
        from_attributes = True


class MCQAnswer(BaseModel):
    """Schema for MCQ answer submission."""
    question_id: int
    answer: str = Field(..., description="Answer option: A, B, C, or D")


class LogicAnswer(BaseModel):
    """Schema for Logic & Trace answer submission."""
    question_id: int
    answer: str = Field(..., description="Exact answer string")


class CodingSubmission(BaseModel):
    """Schema for coding solution submission."""
    question_id: int
    code: str = Field(..., description="User's code solution")
    custom_input: Optional[str] = Field(None, description="Custom input for testing (optional)")


class CustomRunRequest(BaseModel):
    """Schema for custom input code execution."""
    code: str = Field(..., description="User's code")
    custom_input: str = Field(..., description="Custom input to test with")


class SectionProgress(BaseModel):
    """Schema for section progress."""
    section: Optional[str] = None
    current_section: Optional[str] = None
    section_a_completed: bool = False
    section_b_completed: bool = False
    section_c_completed: bool = False
    section_a_score: Optional[float] = None
    section_b_score: Optional[float] = None
    section_c_score: Optional[float] = None


class SectionScore(BaseModel):
    """Schema for section score."""
    section: str
    score: float
    max_score: float
    questions_total: int
    questions_answered: int


class DetailedScore(BaseModel):
    """Schema for detailed scoring breakdown."""
    section_a: SectionScore
    section_b: SectionScore
    section_c: SectionScore
    total_score: float
    max_score: float = 100.0


class AssessmentCompleteResponse(BaseModel):
    """Schema for assessment completion response."""
    assessment_id: int
    total_score: float
    section_a_score: float
    section_b_score: float
    section_c_score: float
    new_elo_rating: int
    completed_at: datetime
    detailed_scores: Optional[DetailedScore] = None
    auto_submitted: Optional[bool] = Field(None, description="True when submitted automatically due to violations")


class SectionCompleteResponse(BaseModel):
    """Schema for section completion response."""
    section: str
    section_score: float
    next_section: Optional[str]
    is_complete: bool


class ViolationLogRequest(BaseModel):
    """Schema for logging an assessment violation."""
    violation_type: str = Field(..., description="Type of violation: 'fullscreen_exit', 'tab_switch', 'window_blur'")
    timestamp: Optional[datetime] = Field(None, description="Client timestamp of violation")


class ViolationLogResponse(BaseModel):
    """Schema for violation log response."""
    violation_count: int
    message: Optional[str] = None


class TimerValidationRequest(BaseModel):
    """Schema for timer validation request."""
    client_time_remaining: int = Field(..., description="Client-reported time remaining in seconds")


class TimerValidationResponse(BaseModel):
    """Schema for timer validation response."""
    is_valid: bool
    server_time_remaining: int
    difference: int = Field(..., description="Difference between server and client time in seconds")
    message: Optional[str] = None


class TestCaseResult(BaseModel):
    """Schema for individual test case result."""
    passed: bool
    input: str
    expected_output: str
    actual_output: str
    error: Optional[str] = None


class TestResultResponse(BaseModel):
    """Schema for test execution response (Run/Test endpoint)."""
    passed: int
    total: int
    results: List[TestCaseResult]
    execution_time: float
    error: Optional[str] = None