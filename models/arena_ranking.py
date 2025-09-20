from database import Base
from sqlalchemy import Column
from token import STRING, FLOAT, DateTime
import datetime

class ArenaRanking(Base):
    
    __tablename__ = "arena_ranking"
    
    id = Column(STRING, primary_key=True, unique=True, nullable=False)
    text = Column(STRING, nullable=False)
    input_text = Column(STRING, nullable=False)
    from_language = Column(STRING, nullable=False)
    to_language = Column(STRING, nullable=False)
    challenge_id = Column(STRING, nullable=False)
    challenge_name = Column(STRING, nullable=False)
    score = Column(FLOAT, default=0.0, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

