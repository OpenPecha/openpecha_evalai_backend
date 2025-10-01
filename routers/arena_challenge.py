from fastapi import APIRouter, Depends, HTTPException, Path, Body, status, Query
from database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging
from models.arena_challege import ArenaChallenge
from models.template_v2 import TemplateV2
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

router = APIRouter(prefix="/arena/challenge", tags=["arena","challenge"])

NUMBER_OF_ITEMS_PER_PAGE = 9

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

def get_template_counts(db: db_dependency, challenge_ids: List[str]) -> Dict[str, int]:
    """Get template counts for a list of challenge IDs using a single optimized query"""
    try:
        if not challenge_ids:
            return {}
        
        # Use a single query with GROUP BY to get all counts at once
        result = db.query(
            TemplateV2.challenge_id,
            func.count(TemplateV2.id).label('count')
        ).filter(
            TemplateV2.challenge_id.in_(challenge_ids),
            (TemplateV2.hidden == False) | (TemplateV2.hidden == None)
        ).group_by(TemplateV2.challenge_id).all()
        
        # Convert result to dictionary
        template_counts = {row.challenge_id: row.count for row in result}
        
        # Ensure all challenge_ids have a count (default to 0 if not found)
        return {challenge_id: template_counts.get(challenge_id, 0) for challenge_id in challenge_ids}
    except Exception as e:
        logger.error(f"Error fetching template counts: {str(e)}")
        return {challenge_id: 0 for challenge_id in challenge_ids}


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
        
        # Get challenge IDs for template counting
        challenge_ids = [challenge.id for challenge in arena_challenge]
        template_counts = get_template_counts(db, challenge_ids)
        
        items = []
        for arena_challenge in arena_challenge:
            items.append(
                ArenaChallengeRead(
                    id=arena_challenge.id,
                    text_category=text_category[arena_challenge.text_category_id],
                    user_id=arena_challenge.user_id,
                    challenge_name=arena_challenge.challenge_name,
                    from_language=arena_challenge.from_language,
                    to_language=arena_challenge.to_language,
                    template_count=template_counts.get(arena_challenge.id, 0)
                )
            )
        return ArenaChallengeListResponse(total_count=total_count, items=items)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("", response_model=ArenaChallengeRead, status_code=status.HTTP_201_CREATED)
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
            to_language=new_arena_challenge.to_language,
            template_count=0  # New challenges start with 0 templates
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{challenge_id}", response_model=ArenaChallengeRead, status_code=status.HTTP_200_OK)
def get_arena_challenge_by_id(
    db: db_dependency,
    challenge_id: str = Path(..., description="Challenge ID"),
):
    """
    Get a single arena challenge by its ID.
    """
    try:
        arena_challenge = db.query(ArenaChallenge).filter(ArenaChallenge.id == challenge_id).first()
        
        if not arena_challenge:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Arena challenge with ID {challenge_id} not found"
            )
        
        text_category: Dict[str, str] = get_text_category(db)
        
        # Get template count for this specific challenge
        template_count = db.query(TemplateV2).filter(
            TemplateV2.challenge_id == challenge_id,
            TemplateV2.hidden == False
        ).count()
        
        return ArenaChallengeRead(
            id=arena_challenge.id,
            text_category=text_category[arena_challenge.text_category_id],
            user_id=arena_challenge.user_id,
            challenge_name=arena_challenge.challenge_name,
            from_language=arena_challenge.from_language,
            to_language=arena_challenge.to_language,
            template_count=template_count
        )   
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching arena challenge {challenge_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


