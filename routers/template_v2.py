from models.arena_challege import ArenaChallenge
from fastapi import APIRouter, Depends, HTTPException, Path, Body, status, Query
from sqlalchemy.orm import Session
from typing import Annotated, List
import logging
from database import get_db

from routers.arena_challenge import get_text_category
from typing import Dict
from models.user import User
from auth import get_current_active_user


from schemas.user import UserBase,UserBaseMinimal

from models.template_v2 import TemplateV2
from schemas.template_v2 import (
    TemplateV2Read,
    TemplateV2Create,
    TemplateV2ListResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/template_v2", tags=["template_v2"])

db_dependency = Annotated[Session, Depends(get_db)]

NUMBER_OF_ITEMS_PER_PAGE = 9

@router.get("", response_model=TemplateV2ListResponse, status_code=status.HTTP_200_OK)
def get_all_template_v2(
    db: db_dependency,
    challenge_id: str = Query(..., description="This is the challenge id of the template"),
    page_number: int = Query(1, description="This is the page number"),
    creator_id: str = Query(None, description="Optional creator user id to filter templates by creator")
):
    try:

        skip = max(0, (page_number - 1) * NUMBER_OF_ITEMS_PER_PAGE)
        limit = NUMBER_OF_ITEMS_PER_PAGE

        base_query = db.query(TemplateV2, User, ArenaChallenge).join(
            User, TemplateV2.user_id == User.id
        ).join(
            ArenaChallenge, TemplateV2.challenge_id == ArenaChallenge.id
        ).filter(TemplateV2.challenge_id == challenge_id)
        
        # Add creator filter if creator_id is provided
        if creator_id:
            base_query = base_query.filter(TemplateV2.user_id == creator_id)

        total_count = base_query.count()

        total_count = total_count // NUMBER_OF_ITEMS_PER_PAGE + (total_count % NUMBER_OF_ITEMS_PER_PAGE > 0)

        templates_with_users_and_challenges = base_query.offset(skip).limit(limit).all()

        text_category: Dict[str, str] = get_text_category(db)

        items = []

        for template, user, challenge in templates_with_users_and_challenges:
            items.append(
                    TemplateV2Read(
                        id=template.id,
                        template_name=template.template_name,
                        user_id=template.user_id,
                        template=template.template,
                        challenge_id=template.challenge_id,
                        text_category=text_category.get(challenge.text_category_id, ""),
                        challenge_name=challenge.challenge_name,
                        from_language=challenge.from_language,
                        to_language=challenge.to_language,
                        created_at=template.created_at,
                        updated_at=template.updated_at,
                        created_by=user.username
                    ))

        return TemplateV2ListResponse(total_count=total_count, items=items)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create", response_model=TemplateV2Read, status_code=status.HTTP_201_CREATED)
def create_template_v2(
    db: db_dependency, 
    template_v2: TemplateV2Create,
    current_user: User = Depends(get_current_active_user)
):
    try:
        new_template_v2 = TemplateV2(
            template_name=template_v2.template_name,
            template=template_v2.template,
            challenge_id=template_v2.challenge_id,
            user_id=current_user.id
        )
        db.add(new_template_v2)
        db.commit()
        db.refresh(new_template_v2)
        logger.info(f"New template created: {new_template_v2}")
        challenge = db.query(ArenaChallenge).filter(ArenaChallenge.id == new_template_v2.challenge_id).first()
        text_category: Dict[str, str] = get_text_category(db)

        return TemplateV2Read(
            id=new_template_v2.id,
            template_name=new_template_v2.template_name,
            user_id=new_template_v2.user_id,
            template=new_template_v2.template,
            challenge_id=challenge.id,
            text_category=text_category[challenge.text_category_id],
            challenge_name=challenge.challenge_name,
            from_language=challenge.from_language,
            to_language=challenge.to_language,
            created_at=new_template_v2.created_at,
            updated_at=new_template_v2.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/update/{template_id}", response_model=TemplateV2Read, status_code=status.HTTP_201_CREATED)
def create_template_v2(
    db: db_dependency, 
    template_v2: TemplateV2Create,
    template_id: str = Path(..., description="This is the id of the template to update"),
    current_user: User = Depends(get_current_active_user)
):
    try:
        template = db.query(TemplateV2).filter(TemplateV2.id == template_id).first()
        if template.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You are not authorized to update this template")
        template.template_name = template_v2.template_name
        template.template = template_v2.template
        template.challenge_id = template_v2.challenge_id
        template.user_id = current_user.id
        db.commit()
        db.refresh(template)
        logger.info(f"Template updated: {template}")

        challenge = db.query(ArenaChallenge).filter(ArenaChallenge.id == template.challenge_id).first()
        text_category: Dict[str, str] = get_text_category(db)

        return TemplateV2Read(
            id=template.id,
            template_name=template.template_name,
            user_id=template.user_id,
            template=template.template,
            challenge_id=challenge.id,
            text_category=text_category[challenge.text_category_id],
            challenge_name=challenge.challenge_name,
            from_language=challenge.from_language,
            to_language=challenge.to_language,
            created_at=template.created_at,
            updated_at=template.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/delete/{template_id}", status_code=status.HTTP_200_OK)
def delete_by_template_id(
    db: db_dependency,
    template_id: str = Path(..., description="This is the id of the template to delete"),
    current_user: User = Depends(get_current_active_user)
):
    try:
        template = db.query(TemplateV2).filter(TemplateV2.id == template_id).first()
        if template.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You are not authorized to delete this template")
        db.delete(template)
        db.commit()
        return {"message": "Template deleted successfully"}
    except Exception:
        raise HTTPException(status_code=404, detail="Template not found in database")

def get_template_response_by_username_and_challenge_id(db: db_dependency, response: List[TemplateV2], text_category: Dict[str, str]):
    templates = []
    for template in response:
        challenge = db.query(ArenaChallenge).filter(ArenaChallenge.id == template.challenge_id).first()
        if challenge is None:
            continue
        templates.append(
            TemplateV2Read(
                id=template.id,
                template_name=template.template_name,
                username=template.username,
                template=template.template,
                challenge_id=challenge.id,
                text_category=text_category[challenge.text_category_id],
                challenge_name=challenge.challenge_name,
                from_language=challenge.from_language,
                to_language=challenge.to_language,
                created_at=template.created_at,
                updated_at=template.updated_at
            )
        )
    return templates