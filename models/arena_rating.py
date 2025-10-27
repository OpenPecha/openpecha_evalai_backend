from database import Base
from sqlalchemy import Column, String, Float, DateTime, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
import datetime
import uuid

class EloRatingByTemplate(Base):

    __tablename__ = "elo_rating_by_template"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    template_id = Column(String, ForeignKey("template_v2.id"), nullable=False)
    challenge_id = Column(String, ForeignKey("arena_challenge.id"), nullable=False)
    elo_rating = Column(Float, default=1000.0, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

    __table_args__ = (UniqueConstraint('template_id', 'challenge_id', name='_template_challenge_uc'),)
    

class EloRatingByModel(Base):

    __tablename__ = "elo_rating_by_model"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    model_name = Column(String, nullable=False)
    challenge_id = Column(String, ForeignKey("arena_challenge.id"), nullable=False)
    elo_rating = Column(Float, default=1000.0, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    __table_args__ = (UniqueConstraint('model_name', 'challenge_id', name='_model_challenge_uc'),)

class EloRatingByModelAndTemplate(Base):

    __tablename__ = "elo_rating_by_model_and_template"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    model_name = Column(String, nullable=False)
    template_id = Column(String, ForeignKey("template_v2.id"), nullable=False)
    challenge_id = Column(String, ForeignKey("arena_challenge.id"), nullable=False)
    elo_rating = Column(Float, default=1000.0, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    
    __table_args__ = (UniqueConstraint('model_name', 'template_id', 'challenge_id', name='_model_template_challenge_uc'),)

class BattleResult(Base):

    __tablename__ = "battle_result"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    template_A_id = Column(String, ForeignKey("template_v2.id"), nullable=False)
    template_B_id = Column(String, ForeignKey("template_v2.id"), nullable=False)
    input_text = Column(String)
    output_text_A = Column(String)
    output_text_B = Column(String)
    model_A = Column(String, nullable=False)
    model_B = Column(String, nullable=False)
    voter_user_id = Column(String, ForeignKey("user.id"), default=None, nullable=True)
    challenge_id = Column(String, ForeignKey("arena_challenge.id"), nullable=False)
    winner_status = Column(String, default=None, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))
    room_id = Column(UUID(as_uuid=True), ForeignKey("room.id"), nullable=True, index=True)