from models.arena_challege import ArenaChallenge
from fastapi import APIRouter, Depends, HTTPException, Path, Body, status, Query
from sqlalchemy.orm import Session
from typing import Annotated, List
import logging
from database import get_db

from models.template_v2 import TemplateV2
from schemas.template_v2 import (
    TemplateV2Read,
    TemplateV2Create
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/template_v2", tags=["template_v2"])

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("/user/{username}", response_model=List[TemplateV2Read], status_code=status.HTTP_200_OK)
def get_all_template_v2_by_username(
    db: db_dependency, 
    challenge_id: str = Query(..., description="This is the challenge id of the template"),
    username: str = Path(..., description="This is the username of the template")
):
    try:
        response = db.query(TemplateV2).filter(
            (TemplateV2.username == username) & (TemplateV2.challenge_id == challenge_id)
        ).all()
        return get_template_response_by_username_and_challenge_id(db, response)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create", response_model=TemplateV2Read, status_code=status.HTTP_201_CREATED)
def create_template_v2(db: db_dependency, template_v2: TemplateV2Create):
    try:
        new_template_v2 = TemplateV2(**template_v2.model_dump())
        db.add(new_template_v2)
        db.commit()
        db.refresh(new_template_v2)
        challenge = db.query(ArenaChallenge).filter(ArenaChallenge.id == new_template_v2.challenge_id).first()
        return TemplateV2Read(
            id=new_template_v2.id,
            template_name=new_template_v2.template_name,
            username=new_template_v2.username,
            template=new_template_v2.template,
            challenge_id=challenge.id,
            text=challenge.text,
            challenge_name=challenge.challenge_name,
            from_language=challenge.from_language,
            to_language=challenge.to_language,
            created_at=new_template_v2.created_at,
            updated_at=new_template_v2.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def get_template_response_by_username_and_challenge_id(db: db_dependency, response: List[TemplateV2]):
    templates = []
    for template in response:
        challenge = db.query(ArenaChallenge).filter(ArenaChallenge.id == template.challenge_id).first()
        templates.append(
            TemplateV2Read(
                id=template.id,
                template_name=template.template_name,
                username=template.username,
                template=template.template,
                challenge_id=challenge.id,
                text=challenge.text,
                challenge_name=challenge.challenge_name,
                from_language=challenge.from_language,
                to_language=challenge.to_language,
                created_at=template.created_at,
                updated_at=template.updated_at
            )
        )
    return templates