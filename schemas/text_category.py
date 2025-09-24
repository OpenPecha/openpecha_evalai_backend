from pydantic import BaseModel

class TextCategoryRead(BaseModel):
    id: str
    name: str

class TextCategoryCreate(BaseModel):
    name: str