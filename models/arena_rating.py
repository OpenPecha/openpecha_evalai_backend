from database import Base
from sqlalchemy import Column, String, Float, DateTime
import datetime
import uuid

class ArenaRating(Base):

    __tablename__ = "arena_rating"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    template_id = Column(String, nullable=False)
    challenge_id = Column(String, nullable=False)
    input_text = Column(String)
    output_text = Column(String)
    score = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

class EloRatingByTemplate(Base):

    __tablename__ = "elo_rating_by_template"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    template_id = Column(String, nullable=False, unique=True)
    challenge_id = Column(String, nullable=False)
    input_text = Column(String)
    output_text = Column(String)
    elo_rating = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

class EloRatingByModel(Base):

    __tablename__ = "elo_rating_by_model"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    model_name = Column(String, nullable=False, unique=True)
    challenge_id = Column(String, nullable=False)
    input_text = Column(String)
    output_text = Column(String)
    elo_rating = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

class EloRatingByModelAndTemplate(Base):

    __tablename__ = "elo_rating_by_model_and_template"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    model_name = Column(String, nullable=False)
    template_id = Column(String, nullable=False)
    challenge_id = Column(String, nullable=False)
    input_text = Column(String)
    output_text = Column(String)
    elo_rating = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

class BattleResult(Base):

    __tablename__ = "battle_result"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), unique=True, nullable=False)
    template_A_id = Column(String, nullable=False)
    template_B_id = Column(String, nullable=False)
    input_text = Column(String)
    output_text_A = Column(String)
    output_text_B = Column(String)
    model_A = Column(String, nullable=False)
    model_B = Column(String, nullable=False)
    challenge_id = Column(String, nullable=False)
    winner_id = Column(String, default=None, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    updated_at = Column(DateTime, nullable=False, default=lambda: datetime.datetime.now(datetime.timezone.utc), onupdate=lambda: datetime.datetime.now(datetime.timezone.utc))

