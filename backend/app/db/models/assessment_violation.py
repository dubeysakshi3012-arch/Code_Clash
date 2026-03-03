"""Assessment violation models for anti-cheating system."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class AssessmentViolation(Base):
    """
    Assessment violation model.
    Tracks user violations during assessment (fullscreen exit, tab switch, etc.)
    """
    
    __tablename__ = "assessment_violations"
    
    id = Column(Integer, primary_key=True, index=True)
    assessment_id = Column(Integer, ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    violation_type = Column(String(50), nullable=False)  # 'fullscreen_exit', 'tab_switch', 'window_blur'
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    assessment = relationship("Assessment", backref="violations")
    user = relationship("User", backref="assessment_violations")
    
    def __repr__(self) -> str:
        return f"<AssessmentViolation(id={self.id}, assessment_id={self.assessment_id}, type={self.violation_type}, timestamp={self.timestamp})>"
