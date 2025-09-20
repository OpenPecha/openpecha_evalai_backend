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