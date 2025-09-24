from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "user"

    id = Column(String, primary_key=True, nullable=False)  # Auth0 user ID as primary key
    username = Column(String, unique=True, index=True, nullable=False)  # Username derived from email
    first_name = Column(String, nullable=True, default='')
    last_name = Column(String, nullable=True, default='')
    email = Column(String, unique=True, index=True, nullable=False)
    picture = Column(String, nullable=True)
    role = Column(String, nullable=False, default='user')  # User role
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    # Relationships (existing)
    translation_jobs = relationship("TranslationJob", back_populates="user")
    votes = relationship("Vote", back_populates="user")
    
    # New relationships for foreign key references
    # These are defined as backrefs in the respective model files:
    # - templates (from Template model)
    # - created_models, updated_models (from Model model)
    # - results, created_results, updated_results (from Result model)
    # - template_v2s (from TemplateV2 model via user_id)
    # - submissions (from Submission model via user_id) 
    # - created_challenges (from Challenge model via created_by)
    # - arena_challenges (from ArenaChallenge model via user_id)
    # - battle_results (from BattleResult model via voter_user_id)
