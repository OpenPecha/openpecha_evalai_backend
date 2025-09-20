from fastapi import APIRouter, Depends, HTTPException, Path, Body, status
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
def get_all_template_v2_by_username(db: db_dependency, username: str = Path(..., description="This is the username of the template")):
    try:
        return db.query(TemplateV2).filter(TemplateV2.username == username).all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
