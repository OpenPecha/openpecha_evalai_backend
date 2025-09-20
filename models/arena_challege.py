from token import STRING, DateTime
from tokenize import String
from sqlalchemy import Column
from database import Base
import datetime

class ArenaChallenge(Base):

    __tablename__ = "arena_challenge"

    id = Column(STRING, primary_key=True, unique=True, nullable=False)
    text = Column(STRING, nullable=False)
    challenge_name = Column(STRING, nullable=False)
    from_language = Column(STRING, nullable=False)
    to_language = Column(STRING, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

