from sqlalchemy import Column, String, DateTime
from database import Base
import datetime
import uuid

class ArenaChallenge(Base):

    __tablename__ = "arena_challenge"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    text = Column(String, nullable=False)
    challenge_name = Column(String, nullable=False)
    from_language = Column(String, nullable=False)
    to_language = Column(String, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

