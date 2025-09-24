from pydantic import BaseModel
from typing import Optional, List
from enum import Enum

class RankingBy(Enum):
    COMBINED = "combined"
    TEMPLATE = "template"
    MODEL = "model"

class ChallengeDetails(BaseModel):
    challenge_id: str
    challenge_name: str
    text_category: str
    from_language: str
    to_language: str

class ArenaRanking(BaseModel):
    template_name: Optional[str] = None
    model_name: Optional[str] = None
    elo_rating: float

class ArenaRankingAll(BaseModel):
    challenge_details: ChallengeDetails
    arena_ranking: List[ArenaRanking]