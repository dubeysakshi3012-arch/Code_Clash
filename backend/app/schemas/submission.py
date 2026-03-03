"""Submission-related Pydantic schemas."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any
from app.db.models.assessment import ProgrammingLanguage
from app.db.models.submission import SubmissionStatus, Verdict


class SubmissionCreate(BaseModel):
    """Schema for creating a submission."""
    source_code: str = Field(..., description="Source code to evaluate")
    language: ProgrammingLanguage = Field(..., description="Programming language")
    problem_id: Optional[int] = Field(None, description="Problem/question ID (optional for generic judge)")
    custom_input: Optional[str] = Field(None, description="Custom input for 'Run Code' feature")


class SubmissionResponse(BaseModel):
    """Schema for submission response."""
    id: int
    user_id: int
    problem_id: Optional[int]
    language: ProgrammingLanguage
    source_code: str
    status: SubmissionStatus
    verdict: Optional[str]
    execution_time: Optional[float]
    memory_usage: Optional[int]
    test_cases_passed: Optional[int]
    total_test_cases: Optional[int]
    execution_result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class SubmissionStatusResponse(BaseModel):
    """Lightweight schema for submission status check."""
    id: int
    status: SubmissionStatus
    verdict: Optional[str]
    test_cases_passed: Optional[int]
    total_test_cases: Optional[int]
    execution_time: Optional[float]
    memory_usage: Optional[int]
    
    class Config:
        from_attributes = True


class SubmissionListResponse(BaseModel):
    """Schema for paginated submission list."""
    submissions: list[SubmissionResponse]
    total: int
    limit: int
    offset: int
