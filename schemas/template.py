from pydantic import BaseModel
from datetime import datetime

class TemplateRead(BaseModel):
    id: str
    template_name: str
    username: str
    template_text: str
    template_score: float
    created_at: datetime
    updated_at: datetime

class TemplateCreate(BaseModel):
    template_name: str
    username: str
    template_text: str