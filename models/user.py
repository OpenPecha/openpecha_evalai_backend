from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "user"

    id = Column(String, primary_key=True, nullable=False)  # Auth0 user ID as primary key
    username = Column(String, unique=True, index=True, nullable=False)  # Username derived from email
    firstName = Column(String, nullable=False)
    lastName = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    picture = Column(String, nullable=True)
    role = Column(String, nullable=False, default='user')  # User role
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    # Relationships
    translation_jobs = relationship("TranslationJob", back_populates="user")
    votes = relationship("Vote", back_populates="user")
