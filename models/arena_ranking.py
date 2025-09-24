from database import Base
from sqlalchemy import Column, String, Float, DateTime
import datetime
import uuid

class ArenaRanking(Base):
    
    __tablename__ = "arena_ranking"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    text = Column(String, nullable=False)
    input_text = Column(String, nullable=False)
    from_language = Column(String, nullable=False)
    to_language = Column(String, nullable=False)
    challenge_id = Column(String, nullable=False)
    challenge_name = Column(String, nullable=False)
    score = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

