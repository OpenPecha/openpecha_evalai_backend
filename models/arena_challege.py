from sqlalchemy import Column, String, DateTime, ForeignKey
from database import Base
import datetime
import uuid


class ArenaChallenge(Base):

    __tablename__ = "arena_challenge"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    text_category_id = Column(String, ForeignKey("text_category.id"), nullable=False)
    user_id = Column(String, ForeignKey("user.id"), nullable=False)
    challenge_name = Column(String, nullable=False)
    from_language = Column(String, nullable=False)
    to_language = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

