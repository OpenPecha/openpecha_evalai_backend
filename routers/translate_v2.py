from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from typing import Annotated, List
import logging
import random
from dotenv import load_dotenv
import os
import json

from models.template_v2 import TemplateV2

from schemas.translate_v2 import (
    TranslateV2Request
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translate_v2", tags=["translate_v2"])

db_dependency = Annotated[Session, Depends(get_db)]


@router.post("", status_code=status.HTTP_200_OK)
def translate_v2(db: db_dependency, request: TranslateV2Request):
    random_template_id_1 = request.template_id if request.template_id else get_random_template_v2(db, [])
    random_template_id_2 = get_random_template_v2(db, [random_template_id_1])

    logger.info(f"random_template_id_1: {random_template_id_1}")
    logger.info(f"random_template_id_2: {random_template_id_2}")

    try:
        template_1 = db.query(TemplateV2).filter(TemplateV2.id == random_template_id_1).first()
        template_2 = db.query(TemplateV2).filter(TemplateV2.id == random_template_id_2).first()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    model_1 = get_random_model_v2()
    model_2 = get_random_model_v2()

    logger.info(f"model_1: {model_1}")
    logger.info(f"model_2: {model_2}")

    translation_1 = generate_translation(db, model_1, template_1, request.input_text)
    translation_2 = generate_translation(db, model_2, template_2, request.input_text)


    
def generate_translation(db: db_dependency, model: str, template: TemplateV2, input_text: str):
    pass


def get_model_providers():
    """Get model providers from environment variable with fallback to default configuration"""
    default_providers = {
                            "claude-3-5-sonnet-20241022": "anthropic",
                            "claude-3-7-sonnet-20250219": "anthropic",
                            "claude-sonnet-4-20250514": "anthropic",
                            "claude-3-5-haiku-20241022": "anthropic",
                            "claude-3-opus-20240229": "anthropic",
                            "gemini-2.5-pro": "google",
                            "gemini-2.5-flash-thinking": "google",
                            "gemini-2.5-flash": "google"
                         }
    
    model_providers_env = os.getenv("MODEL_PROVIDERS")
    if model_providers_env:
        try:
            return json.loads(model_providers_env)
        except json.JSONDecodeError:
            return default_providers
    else:
        return default_providers

def get_random_template_v2(db: db_dependency, exclude_template_id: List[str]):
    try:
        templates = db.query(TemplateV2).filter(TemplateV2.id.not_in(exclude_template_id)).all()
        return random.choice(templates).id
    except:
        return None

def get_random_model_v2():
    model = random.choice(list(get_model_providers().keys()))
    return model