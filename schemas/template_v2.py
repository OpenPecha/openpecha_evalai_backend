from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class TemplateV2Read(BaseModel):
    id: str
    template_name: str
    username: str
    template: str
    challenge_id: str
    text_category: str
    challenge_name: str
    from_language: str
    to_language: str
    created_at: datetime
    updated_at: datetime

class TemplateV2Create(BaseModel):
    id: Optional[str] = None
    template_name: str
    username: str
    template: str
    challenge_id: str