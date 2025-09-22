from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from typing import Annotated, List
import logging
import random
import os
import json
import requests
import difflib

from models.arena_challege import ArenaChallenge
from models.template_v2 import TemplateV2
from models.arena_rating import ArenaRating, BattleResult

from schemas.translate_v2 import (
    TranslateV2Request,
    TranslationResponse,
    UpdateBattleWinnerRequest,
    ResultType
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
    logger.info(f"translation_1: {translation_1}")
    translation_2 = generate_translation(db, model_2, template_2, request.input_text)
    logger.info(f"translation_2: {translation_2}")

    challenger_1 = write_to_arena_rating(
        db, 
        template_id = random_template_id_1, 
        challenge_id =request.challenge_id,
        input_text = request.input_text,
        output_text = translation_1,
        score = 0
    )

    challenger_2 = write_to_arena_rating(
        db,
        template_id = random_template_id_2,
        challenge_id = request.challenge_id,
        input_text = request.input_text,
        output_text = translation_2,
        score = 0
    )

    battle_result = write_battle_result(
        db,
        template_1_id = random_template_id_1,
        template_2_id = random_template_id_2,
        input_text = request.input_text,
        output_text_1 = translation_1,
        output_text_2 = translation_2,
        model_1 = model_1,
        model_2 = model_2,
    )

    return TranslationResponse(
        battle_result_id=battle_result.id,
        id_1=challenger_1.id,
        translation_1=translation_1,
        model_1=model_1,
        translation_2=translation_2,
        id_2=challenger_2.id,
        model_2=model_2
    )

@router.put("/update_battle_winner", status_code=status.HTTP_200_OK)
def update_battle_winner(db: db_dependency, request: UpdateBattleWinnerRequest):
    if request.result is not None:
        challenger_1 = db.query(ArenaRating).filter(ArenaRating.id == request.id_1).first()
        challenger_2 = db.query(ArenaRating).filter(ArenaRating.id == request.id_2).first()

        challenger_1_score = challenger_1.score
        challenger_2_score = challenger_2.score

        new_rating_1, new_rating_2 = get_new_rating_for_both_challengers(challenger_1_score, challenger_2_score, request)

        challenger_1.score = new_rating_1
        challenger_2.score = new_rating_2
        
        # Update the battle result with the winner
        battle_result = db.query(BattleResult).filter(BattleResult.id == request.battle_result_id).first()
        if battle_result:
            battle_result.result = request.result.value  # Convert enum to string value
        
        try:
            db.commit()
            logger.info(f"Updated ELO ratings - Challenger 1: {challenger_1_score} -> {new_rating_1}, Challenger 2: {challenger_2_score} -> {new_rating_2}")
            return {"message": "Battle winner updated successfully", "new_ratings": {"id_1": new_rating_1, "id_2": new_rating_2}}
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating battle winner: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Result is required")

def get_new_rating_for_both_challengers(challenger_1_score: float, challenger_2_score: float, request: UpdateBattleWinnerRequest):
     # Update ELO ratings based on battle result
    if request.result == ResultType.A:
        # Challenger 1 wins
        new_rating_1, new_rating_2 = calculate_elo_rating(challenger_1_score, challenger_2_score, result="win")
    elif request.result == ResultType.B:
        # Challenger 2 wins
        new_rating_2, new_rating_1 = calculate_elo_rating(challenger_2_score, challenger_1_score, result="win")
    elif request.result == ResultType.DRAW:
        # Draw
        new_rating_1, new_rating_2 = calculate_elo_rating(challenger_1_score, challenger_2_score, result="draw")
    elif request.result == ResultType.BOTH_WORST:
        # Both performed worst - special case where both lose rating
        new_rating_1, new_rating_2 = calculate_elo_rating(challenger_1_score, challenger_2_score, result="both_worst")
    else:
        raise HTTPException(status_code=400, detail="Invalid result")
    
    return new_rating_1, new_rating_2


def calculate_elo_rating(rating_a: float, rating_b: float, result: str, k_factor: int = 32) -> tuple[float, float]:
    """
    Calculate new ELO ratings for two players based on battle result.
    
    Args:
        rating_a (float): Current ELO rating of player A
        rating_b (float): Current ELO rating of player B
        result (str): Battle result - "win" (A wins), "draw", or "both_worst"
        k_factor (int): K-factor for ELO calculation (default: 32)
    
    Returns:
        tuple[float, float]: New ratings for player A and player B
    """
    # Calculate expected scores
    expected_a = 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    expected_b = 1 / (1 + 10 ** ((rating_a - rating_b) / 400))
    
    # Determine actual scores based on result
    if result == "win":
        # Player A wins
        actual_a = 1.0
        actual_b = 0.0
    elif result == "draw":
        # Draw
        actual_a = 0.5
        actual_b = 0.5
    elif result == "both_worst":
        # Both performed worst - both lose rating as if they lost to a stronger opponent
        # This is a special case where both players are penalized
        actual_a = 0.0
        actual_b = 0.0
        # Adjust expected scores to make the penalty more significant
        expected_a = 0.7  # Assume they were expected to do better
        expected_b = 0.7
    else:
        raise ValueError(f"Invalid result: {result}. Must be 'win', 'draw', or 'both_worst'")
    
    # Calculate new ratings
    new_rating_a = rating_a + k_factor * (actual_a - expected_a)
    new_rating_b = rating_b + k_factor * (actual_b - expected_b)
    
    # Ensure ratings don't go below a minimum threshold (e.g., 100)
    new_rating_a = max(100, new_rating_a)
    new_rating_b = max(100, new_rating_b)
    
    return round(new_rating_a, 2), round(new_rating_b, 2)



def write_battle_result(db: db_dependency, template_1_id: str, template_2_id: str, input_text: str, output_text_1: dict, output_text_2: dict, model_1: str, model_2: str):
    battle_result = BattleResult(
        template_A_id = template_1_id,
        template_B_id = template_2_id,
        input_text = input_text,
        output_text_A = str(output_text_1),
        output_text_B = str(output_text_2),
        model_A = model_1,
        model_B = model_2
    )
    try:
        db.add(battle_result)
        db.commit()
        db.refresh(battle_result)
        logger.info(f"Written to battle result: {battle_result}")
        return battle_result
    except Exception as e:
        db.rollback()
        logger.error(f"Error writing to battle result: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def write_to_arena_rating(db: db_dependency, template_id: str, challenge_id: str, input_text: str, output_text: dict, score: int):
    arena_rating = ArenaRating(
        template_id = template_id,
        challenge_id = challenge_id,
        input_text = input_text,
        output_text = str(output_text),
        score = score
    )
    try:
        db.add(arena_rating)
        db.commit()
        db.refresh(arena_rating)
        logger.info(f"Written to arena rating: {arena_rating}")
        return arena_rating
    except Exception as e:
        db.rollback()
        logger.error(f"Error writing to arena rating: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
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
    except Exception as e:
        logger.error(f"Error getting random template: {str(e)}")
        return None

def get_random_model_v2():
    model = random.choice(list(get_model_providers().keys()))
    return model
