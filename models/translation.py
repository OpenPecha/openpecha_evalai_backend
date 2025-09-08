from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from database import Base
import datetime
import uuid

class ModelVersion(Base):
    """
    Represents a specific AI model version for translation (e.g., gpt-4o-mini, claude-3-5-sonnet-latest)
    """
    __tablename__ = "model_version"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    version = Column(String, nullable=False, unique=True)  # e.g., "gpt-4o-mini", "claude-3-5-sonnet-latest"
    provider = Column(String, nullable=False)  # e.g., "openai", "anthropic", "google"
    vote_count = Column(Integer, nullable=False, default=0)  # Simple vote counter
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    # Relationships
    outputs = relationship("TranslationOutput", back_populates="model_version")
    votes = relationship("Vote", back_populates="model_version")

class TranslationJob(Base):
    """
    Represents a translation job with source text and optional prompt
    """
    __tablename__ = "translation_job"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    source_text = Column(Text, nullable=False)
    prompt = Column(Text, nullable=True)  # Optional user prompt
    user_id = Column(String, nullable=False)  # User who created the job
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    # Relationships
    outputs = relationship("TranslationOutput", back_populates="job")

class TranslationOutput(Base):
    """
    Represents the output from a specific model for a translation job
    """
    __tablename__ = "translation_output"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    job_id = Column(UUID(as_uuid=True), ForeignKey("translation_job.id"), nullable=False)
    model_version_id = Column(UUID(as_uuid=True), ForeignKey("model_version.id"), nullable=False)
    streamed_text = Column(Text, nullable=False)  # The full translated text
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    # Relationships
    job = relationship("TranslationJob", back_populates="outputs")
    model_version = relationship("ModelVersion", back_populates="outputs")
    votes = relationship("Vote", back_populates="translation_output")

class Vote(Base):
    """
    Represents a user's rating (1-5 stars) for a specific model version and translation output
    """
    __tablename__ = "vote"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    user_id = Column(String, nullable=False)  # User who voted
    model_version_id = Column(UUID(as_uuid=True), ForeignKey("model_version.id"), nullable=False)
    translation_output_id = Column(UUID(as_uuid=True), ForeignKey("translation_output.id"), nullable=False)  # Required reference to specific output
    score = Column(Integer, nullable=False)  # Rating from 1-5
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    # Constraints
    __table_args__ = (
        CheckConstraint('score >= 1 AND score <= 5', name='valid_score_range'),
        UniqueConstraint('user_id', 'model_version_id', name='unique_user_model_vote'),
    )
    
    # Relationships
    model_version = relationship("ModelVersion", back_populates="votes")
    translation_output = relationship("TranslationOutput")
