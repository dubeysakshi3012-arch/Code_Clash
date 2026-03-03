"""Match-related Pydantic schemas."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


class MatchCreateRequest(BaseModel):
    """Request body for internal match creation (Socket server)."""
    participant_user_ids: List[int] = Field(..., min_length=2, max_length=2)
    language: str = Field(..., pattern="^(python|java|cpp)$")
    question_ids: Optional[List[int]] = None
    time_limit_per_question: int = Field(300, ge=60, le=600)


class MatchParticipantSummary(BaseModel):
    user_id: int
    score: Optional[float] = None
    left_at: Optional[datetime] = None
    submissions_count: int = 0

    class Config:
        from_attributes = True


class MatchQuestionSummary(BaseModel):
    question_id: int
    order: int

    class Config:
        from_attributes = True


class MatchListResponse(BaseModel):
    id: int
    status: str
    winner_id: Optional[int] = None
    language: str
    time_limit_per_question: int
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MatchTestRequest(BaseModel):
    """Request body for Run/Test code in a match (no submission)."""
    question_id: int
    code: str = Field(..., max_length=50_000, description="User's code to run")
    custom_input: Optional[str] = Field(None, max_length=10_000, description="Optional custom input for single run")


class MatchSubmitRequest(BaseModel):
    """Submit an answer for a match question."""
    question_id: int
    answer_type: str = Field(..., pattern="^(mcq|logic_trace|coding)$")
    answer_data: Optional[str] = None
    mcq_answer: Optional[str] = None


class MatchSubmitResponse(BaseModel):
    score: float
    is_correct: bool
    match_completed: bool
    winner_id: Optional[int] = None


class MatchCreateResponse(BaseModel):
    """Response after creating a match."""
    match_id: int
    question_ids: List[int]
    time_limit_per_question: int


class MatchDetailResponse(BaseModel):
    id: int
    status: str
    winner_id: Optional[int] = None
    language: str
    time_limit_per_question: int
    server_started_at: Optional[datetime] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    participants: List[MatchParticipantSummary]
    questions: List[MatchQuestionSummary]

    class Config:
        from_attributes = True
