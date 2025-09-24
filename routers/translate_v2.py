from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from typing import Annotated, List, Dict
import logging
import random
import os
import json
import requests
import difflib
import asyncio
from concurrent.futures import ThreadPoolExecutor
import functools
import aiohttp
import os

from models.arena_challege import ArenaChallenge
from models.template_v2 import TemplateV2
from models.arena_rating import (
    ArenaRating, 
    BattleResult,
    EloRatingByTemplate,
    EloRatingByModel,
    EloRatingByModelAndTemplate
)

from schemas.translate_v2 import (
    TranslateV2Request,
    TranslationResponse,
    UpdateBattleWinnerRequest,
    ResultType
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translate_v2", tags=["translate_v2"])

db_dependency = Annotated[Session, Depends(get_db)]

LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://127.0.0.1:8001")

_commentary_cache: Dict[str, List[dict]] = {}


@router.post("", status_code=status.HTTP_200_OK)
async def translate_v2(db: db_dependency, request: TranslateV2Request):
    random_template_id_1 = request.template_id if request.template_id else get_random_template_v2(db, [], request.challenge_id)
    random_template_id_2 = get_random_template_v2(db, [random_template_id_1], request.challenge_id)

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

    async with asyncio.TaskGroup() as tg:
        translation_1_task = tg.create_task(generate_translation_async(db, model_1, template_1, request.input_text))
        translation_2_task = tg.create_task(generate_translation_async(db, model_2, template_2, request.input_text))
    
    translation_1 = translation_1_task.result()
    translation_2 = translation_2_task.result()
    
    logger.info(f"translation_1: {translation_1}")
    logger.info(f"translation_2: {translation_2}")


    battle_result_id = write_to_battle_result(
        db,
        random_template_id_1,
        random_template_id_2,
        request.challenge_id,
        request.input_text,
        translation_1,
        translation_2,
        model_1,
        model_2
    )

    return TranslationResponse(
        battle_result_id=battle_result_id,
        id_1=random_template_id_1,
        translation_1=translation_1,
        model_1=model_1,
        translation_2=translation_2,
        id_2=random_template_id_2,
        model_2=model_2,
        template_1_name=template_1.template_name,
        template_2_name=template_2.template_name
    )


@router.put("/update_battle_winner", status_code=status.HTTP_200_OK)
def update_battle_winner(db: db_dependency, request: UpdateBattleWinnerRequest):
    
    try:
        battle_details = db.query(BattleResult).filter(BattleResult.id == request.battle_result_id).first()
    except Exception:
        raise HTTPException(status_code=404, detail="Battle result not found")

    template_1_id = battle_details.template_A_id
    template_2_id = battle_details.template_B_id
    
    model_1 = battle_details.model_A
    model_2 = battle_details.model_B

    challenge_id = battle_details.challenge_id

    input_text = battle_details.input_text
    output_text_1 = battle_details.output_text_A
    output_text_2 = battle_details.output_text_B

    calculate_and_store_elo_rating(
        db,
        template_1_id,
        template_2_id,
        model_1,
        model_2,
        challenge_id,
        input_text,
        output_text_1,
        output_text_2,
        request.result
    )

def calculate_and_store_elo_rating(db: db_dependency, template_1_id: str, template_2_id: str, model_1: str, model_2: str, challenge_id: str, input_text: str, output_text_1: str, output_text_2: str, result: ResultType):

    try:
        elo_rating_by_template_1 = db.query(EloRatingByTemplate).filter(
            (EloRatingByTemplate.template_id == template_1_id) & (EloRatingByTemplate.challenge_id == challenge_id)
        ).first()
        elo_rating_by_template_2 = db.query(EloRatingByTemplate).filter(
            (EloRatingByTemplate.template_id == template_2_id) & (EloRatingByTemplate.challenge_id == challenge_id)
        ).first()
        elo_rating_by_model_1 = db.query(EloRatingByModel).filter(
            (EloRatingByModel.model_name == model_1) & (EloRatingByModel.challenge_id == challenge_id)
            ).first()
        elo_rating_by_model_2 = db.query(EloRatingByModel).filter(
            (EloRatingByModel.model_name == model_2) & (EloRatingByModel.challenge_id == challenge_id)
            ).first()
        
        elo_rating_1_by_template_and_model = db.query(EloRatingByModelAndTemplate).filter(
            (EloRatingByModelAndTemplate.model_name == model_1) & (EloRatingByModelAndTemplate.template_id == template_1_id) & (EloRatingByModelAndTemplate.challenge_id == challenge_id)
            ).first()
        elo_rating_2_by_template_and_model = db.query(EloRatingByModelAndTemplate).filter(
            (EloRatingByModelAndTemplate.model_name == model_2) & (EloRatingByModelAndTemplate.template_id == template_2_id) & (EloRatingByModelAndTemplate.challenge_id == challenge_id)
            ).first()

        db_add_list = []

        if elo_rating_by_template_1 is None:
            elo_rating_by_template_1 = EloRatingByTemplate(
                template_id=template_1_id,
                challenge_id=challenge_id,
                input_text=input_text,
                output_text=output_text_1,
            )
            db_add_list.append(elo_rating_by_template_1)
        if elo_rating_by_template_2 is None:
            elo_rating_by_template_2 = EloRatingByTemplate(
                template_id=template_2_id,
                challenge_id=challenge_id,
                input_text=input_text,
                output_text=output_text_2,
            )
            db_add_list.append(elo_rating_by_template_2)
        if elo_rating_by_model_1 is None:
            elo_rating_by_model_1 = EloRatingByModel(
                model_name=model_1,
                challenge_id=challenge_id,
                input_text=input_text,
                output_text=output_text_1,
            )
            db_add_list.append(elo_rating_by_model_1)
        if elo_rating_by_model_2 is None:
            elo_rating_by_model_2 = EloRatingByModel(
                model_name=model_2,
                challenge_id=challenge_id,
                input_text=input_text,
                output_text=output_text_2,
            )
            db_add_list.append(elo_rating_by_model_2)
        if elo_rating_1_by_template_and_model is None:
            elo_rating_1_by_template_and_model = EloRatingByModelAndTemplate(
                model_name=model_1,
                template_id=template_1_id,
                challenge_id=challenge_id,
                input_text=input_text,
                output_text=output_text_1,
            )
            db_add_list.append(elo_rating_1_by_template_and_model)
        if elo_rating_2_by_template_and_model is None:
            elo_rating_2_by_template_and_model = EloRatingByModelAndTemplate(
                model_name=model_2,
                template_id=template_2_id,
                challenge_id=challenge_id,
                input_text=input_text,
                output_text=output_text_2,
            )
            db_add_list.append(elo_rating_2_by_template_and_model)
        
        db.add_all(db_add_list)
        db.commit()
        db.refresh(elo_rating_by_template_1)
        db.refresh(elo_rating_by_template_2)
        db.refresh(elo_rating_by_model_1)
        db.refresh(elo_rating_by_model_2)
        db.refresh(elo_rating_1_by_template_and_model)
        db.refresh(elo_rating_2_by_template_and_model)

        logger.info(f"Batch inserted: elo_rating_by_template_1={elo_rating_by_template_1.id}, elo_rating_by_template_2={elo_rating_by_template_2.id}, elo_rating_by_model_1={elo_rating_by_model_1.id}, elo_rating_by_model_2={elo_rating_by_model_2.id}, elo_rating_1_by_template_and_model={elo_rating_1_by_template_and_model.id}, elo_rating_2_by_template_and_model={elo_rating_2_by_template_and_model.id}")

        new_rating_by_template_1, new_rating_by_template_2 = get_new_rating_for_both_challengers(
            elo_rating_by_template_1.elo_rating, 
            elo_rating_by_template_2.elo_rating, 
            result
        )

        new_rating_by_model_1, new_rating_by_model_2 = get_new_rating_for_both_challengers(
            elo_rating_by_model_1.elo_rating, 
            elo_rating_by_model_2.elo_rating, 
            result
        )
        
        new_rating_1_by_template_and_model, new_rating_2_by_template_and_model = get_new_rating_for_both_challengers(
            elo_rating_1_by_template_and_model.elo_rating, 
            elo_rating_2_by_template_and_model.elo_rating, 
            result
        )

        elo_rating_by_template_1.elo_rating = new_rating_by_template_1
        elo_rating_by_template_2.elo_rating = new_rating_by_template_2
        elo_rating_by_model_1.elo_rating = new_rating_by_model_1
        elo_rating_by_model_2.elo_rating = new_rating_by_model_2
        elo_rating_1_by_template_and_model.elo_rating = new_rating_1_by_template_and_model
        elo_rating_2_by_template_and_model.elo_rating = new_rating_2_by_template_and_model
        
        db.commit()
        db.refresh(elo_rating_by_template_1)
        db.refresh(elo_rating_by_template_2)
        db.refresh(elo_rating_by_model_1)
        db.refresh(elo_rating_by_model_2)
        db.refresh(elo_rating_1_by_template_and_model)
        db.refresh(elo_rating_2_by_template_and_model)

        logger.info(f"Batch updated: elo_rating_by_template_1={elo_rating_by_template_1.elo_rating}, elo_rating_by_template_2={elo_rating_by_template_2.elo_rating}, elo_rating_by_model_1={elo_rating_by_model_1.elo_rating}, elo_rating_by_model_2={elo_rating_by_model_2.elo_rating}, elo_rating_1_by_template_and_model={elo_rating_1_by_template_and_model.elo_rating}, elo_rating_2_by_template_and_model={elo_rating_2_by_template_and_model.elo_rating}")

        return "Success"

    except Exception as e:
        db.rollback()
        logger.error(f"Error in batch insert: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    


def get_new_rating_for_both_challengers(challenger_1_score: float, challenger_2_score: float, result: ResultType):
     # Update ELO ratings based on battle result
    if result == ResultType.A:
        # Challenger 1 wins
        new_rating_1, new_rating_2 = calculate_elo_rating(challenger_1_score, challenger_2_score, result="win")
    elif result == ResultType.B:
        # Challenger 2 wins
        new_rating_2, new_rating_1 = calculate_elo_rating(challenger_2_score, challenger_1_score, result="win")
    elif result == ResultType.DRAW:
        # Draw
        new_rating_1, new_rating_2 = calculate_elo_rating(challenger_1_score, challenger_2_score, result="draw")
    elif result == ResultType.BOTH_WORST:
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
    
    # Ensure ratings don't go below a minimum threshold (e.g., 1000)
    new_rating_a = max(1000, new_rating_a)
    new_rating_b = max(1000, new_rating_b)
    
    return round(new_rating_a, 2), round(new_rating_b, 2)



@functools.lru_cache(maxsize=128)
def load_commentaries():
    if not _commentary_cache:
        commentaries_dir = os.path.join(os.path.dirname(__file__), "..", "commentaries_and_sanskrit")
        for json_file in os.listdir(commentaries_dir):
            if json_file.endswith('.json'):
                file_path = os.path.join(commentaries_dir, json_file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    _commentary_cache[json_file] = json.load(f)
    return _commentary_cache

def write_to_battle_result(db: db_dependency, random_template_id_1: str, random_template_id_2: str, challenge_id: str, input_text: str, translation_1: dict, translation_2: dict, model_1: str, model_2: str):

    battle_result = BattleResult(
        template_A_id=random_template_id_1,
        template_B_id=random_template_id_2,
        input_text=input_text,
        output_text_A=str(translation_1),
        output_text_B=str(translation_2),
        model_A=model_1,
        model_B=model_2,
        challenge_id=challenge_id
    )

    try:
        # Batch insert all objects in a single transaction
        db.add(battle_result)
        db.commit()
        
        # Refresh to get the generated IDs
        db.refresh(battle_result)
        
        logger.info(f"Batch inserted: battle_result.id={battle_result.id}")
        return battle_result.id
    except Exception as e:
        db.rollback()
        logger.error(f"Error in batch insert: {str(e)}")
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

    try:
        db_challenge = db.query(ArenaChallenge).filter(ArenaChallenge.id == template.challenge_id).first()
    except Exception as e:
        logger.error(f"Error getting challenge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

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
            "target_language": db_challenge.to_language
        },
        "model_name": model,
        "model_params": {},
        "custom_prompt": template.template
    }

    translation = get_translation(payload)

    return translation

async def generate_translation_async(db: db_dependency, model: str, template: TemplateV2, input_text: str):
    is_ucca_present = check_ucca_present(template.template)
    is_gloss_present = check_gloss_present(template.template)
    is_commentaries_present = check_commentaries_present(template.template)
    is_sanskrit_present = check_sanskrit_present(template.template)

    ucca = None
    gloss = None
    commentaries_1 = None
    commentaries_2 = None
    commentaries_3 = None
    sanskrit = None

    commentaries_and_sanskrit = get_commentaries_and_sanskrit(input_text)
    if is_commentaries_present:
        commentaries_1 = commentaries_and_sanskrit["commentary_1"]
        commentaries_2 = commentaries_and_sanskrit["commentary_2"]
        commentaries_3 = commentaries_and_sanskrit["commentary_3"]
    if is_sanskrit_present:
        sanskrit = commentaries_and_sanskrit["sanskrit_text"]
    
    if not commentaries_and_sanskrit:
        raise HTTPException(status_code=400, detail="No commentaries and sanskrit found")

    # Create tasks for parallel execution
    tasks = []
    
    if is_ucca_present:
        tasks.append(("ucca", get_ucca_async(input_text, commentaries_and_sanskrit, model)))
        
    if is_gloss_present and ucca is not None:
        # Note: gloss depends on ucca, so we'll handle this sequentially if ucca is needed
        pass
    elif is_gloss_present:
        tasks.append(("gloss", get_gloss_async(input_text, commentaries_and_sanskrit, {}, model)))


    # Execute tasks in parallel
    if tasks:
        task_results = await asyncio.gather(*[task for _, task in tasks])
        
        for i, (task_name, _) in enumerate(tasks):
            if task_name == "ucca":
                ucca = task_results[i].get("ucca_graph", None)
                logger.info(f"ucca: {ucca}")
            elif task_name == "gloss":
                gloss = task_results[i].get("glossary", None)
                logger.info(f"gloss: {gloss}")
    
    # Handle gloss if it depends on ucca (sequential execution)
    if is_gloss_present and is_ucca_present and gloss is None:
        gloss_result = await get_gloss_async(input_text, commentaries_and_sanskrit, ucca, model)
        gloss = gloss_result.get("glossary", None)

    combo_key = generate_combo_key(is_ucca_present, is_gloss_present, is_commentaries_present, is_sanskrit_present)

    try:
        db_challenge = db.query(ArenaChallenge).filter(ArenaChallenge.id == template.challenge_id).first()
    except Exception as e:
        logger.error(f"Error getting challenge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    payload = {
        "combo_key": combo_key,
        "input": {
            "source": input_text,
            "commentaries": [
                commentaries_and_sanskrit["commentary_1"] if commentaries_1 else "",
                commentaries_and_sanskrit["commentary_2"] if commentaries_2 else "",
                commentaries_and_sanskrit["commentary_3"] if commentaries_3 else "",
            ],
            "ucca": str(ucca),
            "gloss": str(gloss),
            "sanskrit": commentaries_and_sanskrit["sanskrit_text"] if sanskrit else "",
            "target_language": db_challenge.to_language
        },
        "model_name": model,
        "model_params": {},
        "custom_prompt": template.template
    }

    logger.info(f"Payload: {payload}")

    translation = await get_translation_async(payload)

    return translation


def get_translation(payload: dict):
    try:
        response = requests.post(f"{LANGGRAPH_URL}/workflow/run", json=payload)
        return response.json()
    except Exception as e:
        logger.error(f"Error generating translation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_translation_async(payload: dict):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{LANGGRAPH_URL}/workflow/run", json=payload) as response:
                logger.info(f"Translation response: {response}")
                return await response.json()
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

async def get_gloss_async(input_text: str, commentaries_and_sanskrit: dict, ucca: dict, model: str):
    logger.info(f"Getting Gloss for input text: {input_text}")
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
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{LANGGRAPH_URL}/gloss/generate", json=payload) as response:
                return await response.json()
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

async def get_ucca_async(input_text: str, commentaries_and_sanskrit: dict, model: str):
    logger.info(f"Getting UCCA for input text: {input_text}")
    payload = {
        "input_text": input_text,
        "model_name": model,
        "commentary_1": commentaries_and_sanskrit["commentary_1"],
        "commentary_2": commentaries_and_sanskrit["commentary_2"],
        "commentary_3": commentaries_and_sanskrit["commentary_3"],
        "sanskrit": commentaries_and_sanskrit["sanskrit_text"]
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{LANGGRAPH_URL}/ucca/generate", json=payload) as response:
                return await response.json()
    except Exception as e:
        logger.error(f"Error generating UCCA: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

    
def get_commentaries_and_sanskrit(input_text: str):
    """Optimized version using cached data and better search"""
    commentaries = load_commentaries()
    
    # Use a more efficient search strategy
    for file_data in commentaries.values():
        for entry in file_data:
            root_display_text = entry.get("root_display_text", "")
            # Quick length check before expensive fuzzy matching
            if abs(len(input_text) - len(root_display_text)) / max(len(input_text), len(root_display_text)) > 0.5:
                continue
            if is_fuzzy_match(input_text, root_display_text):
                return entry
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

def get_random_template_v2(db: db_dependency, exclude_template_id: List[str], challenge_id: str):
    try:
        templates = db.query(TemplateV2).filter(TemplateV2.id.not_in(exclude_template_id), TemplateV2.challenge_id == challenge_id).all()
        if not templates:
            raise HTTPException(status_code=400, detail="Not enough templates found for the challenge")
        return random.choice(templates).id
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting random template: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def get_random_model_v2():
    model = random.choice(list(get_model_providers().keys()))
    return model
