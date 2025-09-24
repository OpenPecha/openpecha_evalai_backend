from pydantic import BaseModel
from typing import Optional
from enum import Enum

class ResultType(Enum):
    A = "a"
    B = "b"
    DRAW = "draw"
    BOTH_WORST = "both_worst"

class TranslateV2Request(BaseModel):
    template_id: Optional[str] = None
    challenge_id: str
    input_text: str

class TranslationResponse(BaseModel):
    battle_result_id: str
    id_1: str
    template_1_name: str
    translation_1: dict
    model_1: str
    id_2: str
    template_2_name: str
    translation_2: dict
    model_2: str

class UpdateBattleWinnerRequest(BaseModel):
    battle_result_id: str
    id_1: str
    id_2: str
    result: ResultType