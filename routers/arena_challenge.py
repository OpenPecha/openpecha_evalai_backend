from fastapi import APIRouter, Depends, HTTPException, Path, Body, status, Query
from database import get_db
from sqlalchemy.orm import Session
import logging
from models.arena_challege import ArenaChallenge
from typing import Annotated, List, Optional, Dict

from models.text_category import TextCategory
from models.user import User
from auth import get_current_active_user


from schemas.arena_challenge import (
    ArenaChallengeRead,
    ArenaChallengeCreate,
    ArenaChallengeListResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/arena_challenge", tags=["arena_challenge"])

NUMBER_OF_ITEMS_PER_PAGE = 2

db_dependency = Annotated[Session, Depends(get_db)]

def get_text_category(db: db_dependency) -> Dict[str, str]:
    text_category_by_id = {}
    try:
        text_category = db.query(TextCategory).all()
        for text_category in text_category:
            text_category_by_id[text_category.id] = text_category.name
        return text_category_by_id
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=ArenaChallengeListResponse, status_code=status.HTTP_200_OK)
def get_arena_challenge_by_query(
    db: db_dependency,
    from_language: Optional[str] = Query(default=None, description="From language"),
    to_language: Optional[str] = Query(default=None, description="To language"),
    text_category_id: Optional[str] = Query(default=None, description="Text category id"),
    challenge_name: Optional[str] = Query(default=None, description="Challenge name"),
    page_number: Optional[int] = Query(default=1, description="Page number")
):

    skip = max(0, (page_number - 1) * NUMBER_OF_ITEMS_PER_PAGE)
    limit = NUMBER_OF_ITEMS_PER_PAGE

    try:
        query = db.query(ArenaChallenge)
        if from_language is not None:
            query = query.filter(ArenaChallenge.from_language.ilike(from_language))
        if to_language is not None:
            query = query.filter(ArenaChallenge.to_language.ilike(to_language))
        if text_category_id is not None:
            query = query.filter(ArenaChallenge.text_category_id == text_category_id)
        if challenge_name is not None:
            query = query.filter(ArenaChallenge.challenge_name.ilike(f"%{challenge_name}%"))
        
        total_count = query.count()
        total_count = total_count // NUMBER_OF_ITEMS_PER_PAGE + (total_count % NUMBER_OF_ITEMS_PER_PAGE > 0)
        
        arena_challenge = query.offset(skip).limit(limit).all()
        
        text_category: Dict[str, str] = get_text_category(db)
        
        items = []
        for arena_challenge in arena_challenge:
            items.append(
                ArenaChallengeRead(
                    id=arena_challenge.id,
                    text_category=text_category[arena_challenge.text_category_id],
                    user_id=arena_challenge.user_id,
                    challenge_name=arena_challenge.challenge_name,
                    from_language=arena_challenge.from_language,
                    to_language=arena_challenge.to_language
                )
            )
        return ArenaChallengeListResponse(total_count=total_count, items=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create", response_model=ArenaChallengeRead, status_code=status.HTTP_201_CREATED)
def create_arena_challenge(
    db: db_dependency,
    arena_challenge: ArenaChallengeCreate,
    current_user: User = Depends(get_current_active_user)
):
    try:
        new_arena_challenge = ArenaChallenge(
            text_category_id=arena_challenge.text_category_id,
            user_id=current_user.id,
            challenge_name=arena_challenge.challenge_name,
            from_language=arena_challenge.from_language,
            to_language=arena_challenge.to_language
        )
        db.add(new_arena_challenge)
        db.commit()
        db.refresh(new_arena_challenge)
        text_category: Dict[str, str] = get_text_category(db)
        return ArenaChallengeRead(
            id=new_arena_challenge.id,
            user_id=new_arena_challenge.user_id,
            text_category=text_category[new_arena_challenge.text_category_id],
            challenge_name=new_arena_challenge.challenge_name,
            from_language=new_arena_challenge.from_language,
            to_language=new_arena_challenge.to_language
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


