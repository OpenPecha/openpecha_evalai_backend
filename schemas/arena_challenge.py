from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class ArenaChallengeRead(BaseModel):
    id: str
    text_category: str
    user_id: Optional[str] = None
    challenge_name: str
    from_language: str
    to_language: str
    template_count: int = 0

class ArenaChallengeCreate(BaseModel):
    text_category_id: str
    from_language: str
    to_language: str
    challenge_name: str

class ArenaChallengeListResponse(BaseModel):
    total_count: int
    items: List[ArenaChallengeRead]