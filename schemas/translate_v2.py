from pydantic import BaseModel
from typing import Optional

class TranslateV2Request(BaseModel):
    template_id: Optional[str] = None
    challenge_id: str
    input_text: str

class TranslationResponse(BaseModel):
    id_1: str
    translation_1: dict
    model_1: str
    id_2: str
    translation_2: dict
    model_2: str