"""Database models."""

from app.db.models.user import User, ProgrammingLanguage as UserLanguage
from app.db.models.question import (
    Question,
    QuestionTemplate,
    TestCase,
    DifficultyTag,
    QuestionType,
    AssessmentSection,
    ProgrammingLanguage as QuestionLanguage
)
from app.db.models.assessment import (
    Assessment,
    AssessmentQuestion,
    AssessmentResult,
    AssessmentStatus,
    AssessmentSection as AssessmentSectionModel,
    ProgrammingLanguage as AssessmentLanguage
)
from app.db.models.assessment_violation import AssessmentViolation
from app.db.models.submission import (
    Submission,
    SubmissionStatus,
    Verdict
)
from app.db.models.match import Match, MatchParticipant, MatchQuestion, MatchSubmission, MatchStatus

# Export unified ProgrammingLanguage (all three are identical)
ProgrammingLanguage = AssessmentLanguage

__all__ = [
    "User",
    "UserLanguage",
    "Question",
    "QuestionTemplate",
    "TestCase",
    "DifficultyTag",
    "QuestionType",
    "AssessmentSection",
    "QuestionLanguage",
    "Assessment",
    "AssessmentQuestion",
    "AssessmentResult",
    "AssessmentSectionModel",
    "AssessmentStatus",
    "AssessmentLanguage",
    "ProgrammingLanguage",  # Unified export
    "AssessmentViolation",
    "Submission",
    "SubmissionStatus",
    "Verdict",
    "Match",
    "MatchParticipant",
    "MatchQuestion",
    "MatchSubmission",
    "MatchStatus",
]
