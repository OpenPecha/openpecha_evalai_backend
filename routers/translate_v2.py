from operator import ge
from turtle import ht
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from typing import Annotated, List
import logging
import random
from dotenv import load_dotenv
import os
import json
import requests
import difflib

from models.arena_challege import ArenaChallenge
from models.template_v2 import TemplateV2

from schemas.translate_v2 import (
    TranslateV2Request,
    TranslationResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translate_v2", tags=["translate_v2"])

db_dependency = Annotated[Session, Depends(get_db)]

LANGGRAPH_URL = "http://127.0.0.1:8001"


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

    return TranslationResponse(
        translation_1=translation_1,
        translation_2=translation_2
    )


    
def generate_translation(db: db_dependency, model: str, template: TemplateV2, input_text: str):
    is_ucca_present = check_ucca_present(template.template)
    is_gloss_present = check_gloss_present(template.template)
    is_commentaries_present = check_commentaries_present(template.template)
    is_sanskrit_present = check_sanskrit_present(template.template)

    ucca = None
    gloss = None

    commentaries_and_sanskrit = get_commentaries_and_sanskrit(input_text)
    if not commentaries_and_sanskrit:
        raise HTTPException(status_code=400, detail="No commentaries and sanskrit found")

    if is_ucca_present:
        ucca = get_ucca(input_text, commentaries_and_sanskrit, model)
        ucca = ucca.get("ucca_graph", None)
        
    if is_gloss_present:
        gloss = get_gloss(input_text, commentaries_and_sanskrit, ucca, model)
        gloss = gloss.get("glossary", None)

    combo_key = generate_combo_key(is_ucca_present, is_gloss_present, is_commentaries_present, is_sanskrit_present)

    challenge = db.query(ArenaChallenge).filter(ArenaChallenge.id == template.challenge_id).first()

    payload = {
        "combo_key": combo_key,
        "input": {
            "source": input_text,
            "commentaries": [
                commentaries_and_sanskrit["commentary_1"],
                commentaries_and_sanskrit["commentary_2"],
                commentaries_and_sanskrit["commentary_3"]
            ],
            "ucca": str(ucca),
            "gloss": str(gloss),
            "sanskrit": commentaries_and_sanskrit["sanskrit_text"],
            "target_language": challenge.to_language
        },
        "model_name": model,
        "model_params": {},
        "custom_prompt": template.template
    }

    translation = get_translation(payload)

    return translation


def get_translation(payload: dict):
    try:
        response = requests.post(f"{LANGGRAPH_URL}/workflow/run", json=payload)
        return response.json()
    except Exception as e:
        logger.error(f"Error generating translation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
def generate_combo_key(is_ucca_present, is_gloss_present, is_commentaries_present, is_sanskrit_present):
    combo_key = ""
    if is_ucca_present:
        combo_key += "ucca"
    if is_gloss_present:
        combo_key += "+gloss"
    if is_commentaries_present:
        combo_key += "+commentaries"
    if is_sanskrit_present:
        combo_key += "+sanskrit"
    return combo_key

def get_gloss(input_text: str, commentaries_and_sanskrit: dict, ucca: dict, model: str):
    payload = {
        "input_text": input_text,
        "model_name": model,
        "model_params": {},
        "ucca_interpretation": str(ucca),
        "commentary_1": commentaries_and_sanskrit["commentary_1"],
        "commentary_2": commentaries_and_sanskrit["commentary_2"],
        "commentary_3": commentaries_and_sanskrit["commentary_3"],
        "sanskrit_text": commentaries_and_sanskrit["sanskrit_text"]
    }
    try:
        response = requests.post(f"{LANGGRAPH_URL}/gloss/generate", json=payload)
        return response.json()
    except Exception as e:
        logger.error(f"Error generating Gloss: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def get_ucca(input_text: str, commentaries_and_sanskrit: dict, model: str):
    payload = {
        "input_text": input_text,
        "model_name": model,
        "commentary_1": commentaries_and_sanskrit["commentary_1"],
        "commentary_2": commentaries_and_sanskrit["commentary_2"],
        "commentary_3": commentaries_and_sanskrit["commentary_3"],
        "sanskrit": commentaries_and_sanskrit["sanskrit_text"]
    }
    try:
        response = requests.post(f"{LANGGRAPH_URL}/ucca/generate", json=payload)
        return response.json()
    except Exception as e:
        logger.error(f"Error generating UCCA: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    
def get_commentaries_and_sanskrit(input_text: str):
    """
    Go through every file in the commentaries_and_sanskrit folder and print every object inside it.
    """
    commentaries_dir = os.path.join(os.path.dirname(__file__), "..", "commentaries_and_sanskrit")
    # List all files in the directory
    try:
        files = [f for f in os.listdir(commentaries_dir) if f.endswith('.json')]
    except Exception as e:
        logger.error(f"Error listing files in directory {commentaries_dir}: {str(e)}")
        return

    for json_file in files:
        file_path = os.path.join(commentaries_dir, json_file)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for entry in data:
                root_display_text = entry.get("root_display_text", "")
                if is_fuzzy_match(input_text, root_display_text):
                    return entry
            
        except FileNotFoundError:
            logger.warning(f"Commentary file not found: {file_path}")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON file: {file_path}")
        except Exception as e:
            logger.error(f"Error reading commentary file {file_path}: {str(e)}")
    
    return None

def is_fuzzy_match(input_text: str, root_display_text: str, threshold: float = 0.7) -> bool:
    similarity = difflib.SequenceMatcher(None, input_text, root_display_text).ratio()
    return similarity > threshold

def check_ucca_present(template: str):
    return "{ucca}" in template

def check_gloss_present(template: str):
    return "{gloss}" in template

def check_commentaries_present(template: str):
    return "{commentaries}" in template

def check_sanskrit_present(template: str):
    return "{sanskrit}" in template



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
