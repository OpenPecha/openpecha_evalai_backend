from pydantic import BaseModel
from datetime import datetime

class TemplateV2Read(BaseModel):
    id: str
    template_name: str
    username: str
    template: str
    challenge_id: str
    created_at: datetime
    updated_at: datetime

class TemplateV2Create(BaseModel):
    template_name: str
    username: str
    template: str
    challenge_id: str