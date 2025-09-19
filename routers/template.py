from fastapi import APIRouter, Depends, status, HTTPException, Path, Body
from sqlalchemy.orm import Session
from typing import Annotated, List
import logging
from database import get_db
from dotenv import load_dotenv
from models.user import User

from models.template import Template
from schemas.template import (
    TemplateRead,
    TemplateCreate
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])

db_dependency = Annotated[Session, Depends(get_db)]

@router.get("", response_model=List[TemplateRead], status_code=status.HTTP_200_OK)
async def list_all_templates(db: db_dependency):
    try:
        return db.query(Template).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{username}", response_model=List[TemplateRead], status_code=status.HTTP_200_OK)
async def list_all_templates_by_username(db: db_dependency, username: str = Path(..., description="This is the username of the template")):
    try:
        return db.query(Template).filter(Template.username == username).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{template_id}", response_model=TemplateRead, status_code=status.HTTP_200_OK)
async def get_template_by_id(db: db_dependency, template_id: str = Path(..., description="This is the id of the template")):
    try:
        template = db.query(Template).filter(Template.id == template_id).first()
        return TemplateRead(
            id=template.id,
            template_name=template.template_name,
            username=template.username,
            template_text=template.template_text,
            template_score=template.template_score,
            created_at=template.created_at,
            updated_at=template.updated_at
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create", response_model=TemplateRead, status_code=status.HTTP_201_CREATED)
async def create_template(
    db: db_dependency, 
    template: TemplateCreate = Body(
        ..., 
        description="This is the template to create",
        example={
            "template_name": "Template 1",
            "username": "john.doe",
            "template_text": "This is the template text"
        }
    )
):
    is_valid_username = db.query(User).filter(User.username == template.username).first()
    if not is_valid_username:
        raise HTTPException(status_code=400, detail="Invalid username")
    try:
        template = Template(
            template_name=template.template_name,
            username=template.username,
            template_text=template.template_text
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        return template
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{template_id}", status_code=status.HTTP_200_OK)
async def delete_template(db: db_dependency, template_id: str = Path(..., description="This is the id of the template")):
    try:
        template = db.query(Template).filter(Template.id == template_id).first()
        db.delete(template)
        db.commit()
        return {"message": "Template deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

