from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ArenaChallengeRead(BaseModel):
    id: str
    text_category: str
    user_id: Optional[str] = None
    challenge_name: str
    from_language: str
    to_language: str

class ArenaChallengeCreate(BaseModel):
    text_category_id: str
    from_language: str
    to_language: str
    challenge_name: str