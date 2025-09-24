from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db

from typing import List, Annotated

from models.text_category import TextCategory
from schemas.text_category import (
    TextCategoryRead,
    TextCategoryCreate
)

import logging

logger = logging.getLogger(__name__)

db_dependency = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/text_category", tags=["text_category"])

@router.get("", response_model=List[TextCategoryRead], status_code=status.HTTP_200_OK)
def get_all_text_categories(db: db_dependency):
    try:
        return db.query(TextCategory).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("", response_model=TextCategoryRead, status_code=status.HTTP_201_CREATED)
def create_text_category(db: db_dependency, text_category: TextCategoryCreate):
    try:
        text_category_instance = TextCategory(**text_category.model_dump())
        db.add(text_category_instance)
        db.commit()
        db.refresh(text_category_instance)
        return text_category_instance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))