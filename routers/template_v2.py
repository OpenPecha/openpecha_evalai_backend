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


from schemas.user import UserBase

from models.template_v2 import TemplateV2
from schemas.template_v2 import (
    TemplateV2Read,
    TemplateV2Create,
    TemplateV2WithUser
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/template_v2", tags=["template_v2"])

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("/all", response_model=List[TemplateV2WithUser], status_code=status.HTTP_200_OK)
def get_all_template_v2(
    db: db_dependency,
    challenge_id: str = Query(..., description="This is the challenge id of the template"),
    page_number: int = Query(1, description="This is the page number")
):
    try:

        skip = max(0, (page_number - 1) * 10)
        limit = 10

        templates_with_users_and_challenges = db.query(TemplateV2, User, ArenaChallenge).join(
            User, TemplateV2.user_id == User.id
        ).join(
            ArenaChallenge, TemplateV2.challenge_id == ArenaChallenge.id
        ).filter(TemplateV2.challenge_id == challenge_id).offset(skip).limit(limit).all()

        text_category: Dict[str, str] = get_text_category(db)

        response = []

        for template, user, challenge in templates_with_users_and_challenges:
            response.append(
                TemplateV2WithUser(
                    user_detail=UserBase(
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name,
                        email=user.email,
                        picture=user.picture,
                        role=user.role
                    ),
                    template_detail=TemplateV2Read(
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
                        updated_at=template.updated_at
                    )
                )
            )

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# @router.get("/user/{username}", response_model=List[TemplateV2Read], status_code=status.HTTP_200_OK)
# def get_all_template_v2_by_username(
#     db: db_dependency, 
#     challenge_id: str = Query(..., description="This is the challenge id of the template"),
#     username: str = Path(..., description="This is the username of the template")
# ):
#     try:
#         response = db.query(TemplateV2).filter(
#             (TemplateV2.username == username) & (TemplateV2.challenge_id == challenge_id)
#         ).all()
#         text_category: Dict[str, str] = get_text_category(db)
#         return get_template_response_by_username_and_challenge_id(db, response, text_category)
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))

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

@router.delete("/delete/{template_id}", status_code=status.HTTP_200_OK)
def delete_by_template_id(
    db: db_dependency,
    template_id: str = Path(..., description="This is the id of the template to delete")
):
    try:
        template = db.query(TemplateV2).filter(TemplateV2.id == template_id).first()
        db.delete(template)
        db.commit()
        return {"message": "Template deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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