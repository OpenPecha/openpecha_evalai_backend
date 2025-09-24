from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from schemas.user import UserBase, UserRead


class TemplateV2Read(BaseModel):
    id: str
    template_name: str
    user_id: str
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
    template: str
    challenge_id: str

class TemplateV2WithUser(BaseModel):
    user_detail: UserRead
    template_detail: TemplateV2Read