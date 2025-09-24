from pydantic import BaseModel
from datetime import datetime

class ArenaChallengeRead(BaseModel):
    id: str
    text_category: str
    challenge_name: str
    from_language: str
    to_language: str

class ArenaChallengeCreate(BaseModel):
    text_category_id: str
    from_language: str
    to_language: str
    challenge_name: str