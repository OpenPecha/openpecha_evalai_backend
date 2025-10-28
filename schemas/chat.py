from pydantic import BaseModel
from typing import List, Optional
import datetime


class BattleResultResponse(BaseModel):
    """Schema for battle result in chat detail"""
    id: str
    template_A_id: str
    template_B_id: str
    input_text: Optional[str] = None
    output_text_A: Optional[str] = None
    output_text_B: Optional[str] = None
    model_A: str
    model_B: str
    challenge_id: str
    winner_status: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class RoomResponse(BaseModel):
    """Schema for room in chat history list"""
    id: str
    user_id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    title: str = "Untitled"  # First battle's input text
    battle_count: int = 0  # Number of battles in this room
    last_battle_date: Optional[datetime.datetime] = None  # Date of most recent battle

    class Config:
        from_attributes = True


class RoomDetailResponse(BaseModel):
    """Schema for room detail with all battle results"""
    id: str
    user_id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    battle_results: List[BattleResultResponse] = []

    class Config:
        from_attributes = True

