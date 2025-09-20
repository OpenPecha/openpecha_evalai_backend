from fastapi import APIRouter, Depends, HTTPException, Path, Body, status, Query
from database import get_db
from sqlalchemy.orm import Session
import logging
from models.arena_challege import ArenaChallenge
from typing import Annotated, List, Optional



from schemas.arena_challenge import (
    ArenaChallengeRead,
    ArenaChallengeCreate
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/arena_challenge", tags=["arena_challenge"])

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("/all", response_model=List[ArenaChallengeRead], status_code=status.HTTP_200_OK)
def get_all_arena_challenges(db: db_dependency):
    try:
        return db.query(ArenaChallenge).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("", response_model=List[ArenaChallengeRead], status_code=status.HTTP_200_OK)
def get_arena_challenge_by_query(
    db: db_dependency,
    from_language: Optional[str] = Query(default="bo", description="From language"),
    to_language: Optional[str] = Query(default=None, description="To language"),
    text: Optional[str] = Query(default=None, description="Text"),
    challenge_name: Optional[str] = Query(default=None, description="Challenge name"),
):
    try:
        query = db.query(ArenaChallenge)
        if from_language is not None:
            query = query.filter(ArenaChallenge.from_language == from_language)
        if to_language is not None:
            query = query.filter(ArenaChallenge.to_language == to_language)
        if text is not None:
            query = query.filter(ArenaChallenge.text == text)
        if challenge_name is not None:
            query = query.filter(ArenaChallenge.challenge_name == challenge_name)
        return query.all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create", response_model=ArenaChallengeRead, status_code=status.HTTP_201_CREATED)
def create_arena_challenge(
    db: db_dependency,
    arena_challenge: ArenaChallengeCreate,
):
    try:
        new_arena_challenge = ArenaChallenge(**arena_challenge.model_dump())
        db.add(new_arena_challenge)
        db.commit()
        db.refresh(new_arena_challenge)
        return new_arena_challenge
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


