from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from database import Base
from .user import User
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

class TranslationJob(Base):
    """
    Represents a translation job with source text and optional prompt
    """
    __tablename__ = "translation_job"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    source_text = Column(Text, nullable=False)
    prompt = Column(Text, nullable=True)  # Optional user prompt
    template = Column(Text, nullable=True)  # Template used for translation
    target_language = Column(String, nullable=True)  # Optional target language
    user_id = Column(String, ForeignKey("user.id"), nullable=False)  # User who created the job
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="translation_jobs")
    outputs = relationship("TranslationOutput", back_populates="job")
    votes = relationship("Vote", back_populates="translation_job")

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

class Vote(Base):
    """
    Represents a user's preference vote when comparing two translation outputs.
    Optimized for efficient leaderboard queries and analytics.
    """
    __tablename__ = "vote"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True, nullable=False)
    user_id = Column(String, ForeignKey("user.id"), nullable=False)  # User who voted
    translation_job_id = Column(UUID(as_uuid=True), ForeignKey("translation_job.id"), nullable=False)  # Context: which job/prompt this comparison is for
    
    # Normalized comparison pair: always store smaller UUID first to prevent duplicates
    translation_output_a_id = Column(UUID(as_uuid=True), ForeignKey("translation_output.id"), nullable=False)  # Smaller UUID (lexicographically)
    translation_output_b_id = Column(UUID(as_uuid=True), ForeignKey("translation_output.id"), nullable=False)  # Larger UUID (lexicographically)
    
    # Simplified preference tracking
    winner_id = Column(UUID(as_uuid=True), ForeignKey("translation_output.id"), nullable=True)  # NULL if tie/no preference
    is_tie = Column(Integer, nullable=False, default=0)  # 0=clear winner, 1=tie/both selected, 2=neither selected
    
    # Analytics metadata
    response_time_ms = Column(Integer, nullable=True)  # Time taken to make decision (milliseconds)
    comment = Column(Text, nullable=True)  # Optional user comment about the vote decision
    
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    # Constraints
    __table_args__ = (
        # Ensure user can only vote once per normalized comparison pair
        UniqueConstraint('user_id', 'translation_output_a_id', 'translation_output_b_id', name='unique_user_normalized_comparison'),
        # Ensure translation outputs are different
        CheckConstraint('translation_output_a_id != translation_output_b_id', name='different_translation_outputs'),
        # Ensure proper UUID ordering (A < B lexicographically)
        CheckConstraint('translation_output_a_id < translation_output_b_id', name='normalized_uuid_order'),
        # Ensure winner is one of the compared outputs (if not tie)
        CheckConstraint('winner_id IS NULL OR winner_id = translation_output_a_id OR winner_id = translation_output_b_id', name='valid_winner'),
    )
    
    # Relationships
    user = relationship("User", back_populates="votes")
    translation_job = relationship("TranslationJob", foreign_keys=[translation_job_id])
    translation_output_a = relationship("TranslationOutput", foreign_keys=[translation_output_a_id])
    translation_output_b = relationship("TranslationOutput", foreign_keys=[translation_output_b_id])
    winner = relationship("TranslationOutput", foreign_keys=[winner_id])
