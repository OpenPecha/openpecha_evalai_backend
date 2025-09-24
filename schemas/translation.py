import uuid
import datetime
from pydantic import BaseModel, Field
from typing import Optional, List, Dict

# Constants
TEXT_TO_TRANSLATE_DESC = "Text to translate"
OPTIONAL_PROMPT_DESC = "Optional translation prompt"

# ModelVersion schemas
class ModelVersionBase(BaseModel):
    version: str = Field(..., description="Model version name (e.g., gpt-4o-mini)")
    provider: str = Field(..., description="Provider name (e.g., openai, anthropic, google)")

class ModelVersionCreate(ModelVersionBase):
    pass

class ModelVersionRead(ModelVersionBase):
    id: uuid.UUID
    created_at: datetime.datetime
    
    class Config:
        from_attributes = True

# TranslationJob schemas
class TranslationJobBase(BaseModel):
    source_text: str = Field(..., description=TEXT_TO_TRANSLATE_DESC)
    prompt: Optional[str] = Field(None, description=OPTIONAL_PROMPT_DESC)
    template: Optional[str] = Field(None, description="Template used for translation")
    target_language: Optional[str] = Field(None, description="Target language for translation")

class TranslationJobCreate(TranslationJobBase):
    pass

class TranslationJobRead(TranslationJobBase):
    id: uuid.UUID
    user_id: str
    created_at: datetime.datetime
    
    class Config:
        from_attributes = True

# TranslationOutput schemas
class TranslationOutputBase(BaseModel):
    streamed_text: str = Field(..., description="The translated text")

class TranslationOutputCreate(TranslationOutputBase):
    job_id: uuid.UUID
    model_version_id: uuid.UUID

class TranslationOutputRead(TranslationOutputBase):
    id: uuid.UUID
    job_id: uuid.UUID
    model_version_id: uuid.UUID
    created_at: datetime.datetime
    
    class Config:
        from_attributes = True

# Vote schemas
class VoteBase(BaseModel):
    value: Optional[str] = Field(None, description="Vote value: 'up', 'down', or null")

class VoteCreate(BaseModel):
    translation_output_id: uuid.UUID = Field(..., description="ID of the translation output being voted on")
    vote: Optional[str] = Field(None, description="Vote value: 'up', 'down', or null")

class VoteRead(VoteBase):
    id: uuid.UUID
    model_version_id: uuid.UUID
    translation_output_id: uuid.UUID
    user_id: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    
    class Config:
        from_attributes = True

# Translation request schemas
class TranslationRequest(BaseModel):
    text: str = Field(..., description=TEXT_TO_TRANSLATE_DESC)
    prompt: Optional[str] = Field(None, description=OPTIONAL_PROMPT_DESC)
    template_id: str = Field(..., description="Template id to be used for translation")
    target_language: Optional[str] = Field(None, description="Target language for translation")

class MultiTranslationRequest(BaseModel):
    text: str = Field(..., description=TEXT_TO_TRANSLATE_DESC)
    prompt: Optional[str] = Field(None, description=OPTIONAL_PROMPT_DESC)
    template_id: str = Field(..., description="Template id to be used for translation")
    target_language: Optional[str] = Field(None, description="Target language for translation")
    models: List[str] = Field(..., description="List of model versions to use", min_items=2, max_items=2)

# Leaderboard schemas
class LeaderboardEntry(BaseModel):
    model_version: str = Field(..., description="Model version name")
    provider: str = Field(..., description="Provider name")
    total_votes: int = Field(..., description="Total number of votes received")
    average_score: float = Field(..., description="Average rating score (1.0 to 5.0)")
    score_percentage: float = Field(..., description="Score as percentage (0-100%)")
    score_breakdown: Dict[int, int] = Field(..., description="Count of each star rating (1-5)")

class LeaderboardResponse(BaseModel):
    leaderboard: List[LeaderboardEntry] = Field(..., description="Ordered list of model performances")

# Vote schemas
class VoteRequest(BaseModel):
    score: int = Field(..., description="Rating score from 1-5 stars", ge=1, le=5)

class VoteResponse(BaseModel):
    message: str = Field(..., description="Success message")
    model_version: str = Field(..., description="Model version that was voted on")
    user_score: int = Field(..., description="Score given by the user")
    average_score: float = Field(..., description="Updated average score for this model")
    total_votes: int = Field(..., description="Total number of votes for this model")
    score_percentage: float = Field(..., description="Score as percentage (average/5 * 100)")

# Model suggestion schemas
class ModelSuggestionResponse(BaseModel):
    model_a: str = Field(..., description="First suggested model version")
    model_b: str = Field(..., description="Second suggested model version")
    selection_method: Optional[str] = Field(None, description="Method used for selection (e.g., weighted_random)")
    source_text: Optional[str] = Field(None, description="Source text used for filtering already used models")
    used_models: Optional[List[str]] = Field(None, description="List of models already used with this source text")
    total_combinations: Optional[int] = Field(None, description="Number of model combinations considered")
    note: Optional[str] = Field(None, description="Additional information about the selection process")
