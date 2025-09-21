from pydantic import BaseModel
from typing import Optional

class TranslateV2Request(BaseModel):
    template_id: Optional[str] = None
    challenge_id: str
    input_text: str