from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from database import get_db
from typing import Annotated, Dict
import logging
from typing import List

from models.arena_challege import ArenaChallenge
from models.template_v2 import TemplateV2
from models.arena_rating import (
    EloRatingByTemplate,
    EloRatingByModel,
    EloRatingByModelAndTemplate
)
from schemas.arena_ranking import (
    ChallengeDetails, 
    ArenaRanking,
    ArenaRankingAll,
    RankingBy
)

logger = logging.getLogger(__name__)

db_dependency = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/arena_ranking", tags=["arena_ranking"])


@router.get("/all", response_model=List[ArenaRankingAll], status_code=status.HTTP_200_OK)
def get_all_arena_ranking(db: db_dependency):
    try:
        arena_ranking_all = db.query(EloRatingByModelAndTemplate, TemplateV2.template_name).join(
            TemplateV2, EloRatingByModelAndTemplate.template_id == TemplateV2.id
        ).all()

        ranking_by_challenge_id = get_ranking_by_challenge_id_with_template_names(arena_ranking_all)

        challenge_details_dict = get_challenge_details_dict(db)
        
        response = generate_ranking_all_response_with_template_names(challenge_details_dict, ranking_by_challenge_id)

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{challenge_id}", response_model=ArenaRankingAll, status_code=status.HTTP_200_OK)
def get_arena_ranking_by_challenge_id(
    db: db_dependency, 
    challenge_id: str,
    ranking_by: RankingBy = Query(default=RankingBy.COMBINED, description="This is the ranking by")
):

    try:
        if ranking_by == RankingBy.COMBINED:
            arena_ranking_db = db.query(EloRatingByModelAndTemplate, TemplateV2.template_name).join(
                TemplateV2, EloRatingByModelAndTemplate.template_id == TemplateV2.id
            ).filter(EloRatingByModelAndTemplate.challenge_id == challenge_id).all()
            arena_ranking_list = [
                ArenaRanking(
                    template_name=template_name,
                    model_name=rating.model_name,
                    elo_rating=rating.elo_rating
                ) for rating, template_name in arena_ranking_db
            ]
        elif ranking_by == RankingBy.TEMPLATE:
            arena_ranking_db = db.query(EloRatingByTemplate, TemplateV2.template_name).join(
                TemplateV2, EloRatingByTemplate.template_id == TemplateV2.id
            ).filter(EloRatingByTemplate.challenge_id == challenge_id).all()
            arena_ranking_list = [
                ArenaRanking(
                    template_name=template_name,
                    model_name=None,
                    elo_rating=rating.elo_rating
                ) for rating, template_name in arena_ranking_db
            ]
        elif ranking_by == RankingBy.MODEL:
            arena_ranking_db = db.query(EloRatingByModel).filter(EloRatingByModel.challenge_id == challenge_id).all()
            arena_ranking_list = [
                ArenaRanking(
                    template_name=None,
                    model_name=ranking.model_name,
                    elo_rating=ranking.elo_rating
                ) for ranking in arena_ranking_db
            ]

        challenge_detail = db.query(ArenaChallenge).filter(ArenaChallenge.id == challenge_id).first()

        response = ArenaRankingAll(
            challenge_details=ChallengeDetails(
                challenge_id=challenge_id,
                challenge_name=challenge_detail.challenge_name,
                text=challenge_detail.text,
                from_language=challenge_detail.from_language,
                to_language=challenge_detail.to_language
            ),
            arena_ranking=arena_ranking_list
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def generate_ranking_all_response(challenge_details_dict: Dict[str, ChallengeDetails], ranking_by_challenge_id: Dict[str, List[EloRatingByModelAndTemplate]]):
    response = []
    for challenge_id, ranking in ranking_by_challenge_id.items():
        challenge_details = challenge_details_dict[challenge_id]
        challenge_details_model = ChallengeDetails(
            challenge_id=challenge_id,
            challenge_name=challenge_details["challenge_name"],
            text=challenge_details["text"],
            from_language=challenge_details["from_language"],
            to_language=challenge_details["to_language"]
        )
        arena_ranking_model = []
        for ranking in ranking:
            arena_ranking_model.append(ArenaRanking(
                template_name=ranking.template_id,
                model_name=ranking.model_name,
                elo_rating=ranking.elo_rating
            ))
        response.append(ArenaRankingAll(
            challenge_details=challenge_details_model,
            arena_ranking=arena_ranking_model
        ))
    return response

def generate_ranking_all_response_with_template_names(challenge_details_dict: Dict[str, ChallengeDetails], ranking_by_challenge_id):
    response = []
    for challenge_id, rankings in ranking_by_challenge_id.items():
        challenge_details = challenge_details_dict[challenge_id]
        challenge_details_model = ChallengeDetails(
            challenge_id=challenge_id,
            challenge_name=challenge_details["challenge_name"],
            text=challenge_details["text"],
            from_language=challenge_details["from_language"],
            to_language=challenge_details["to_language"]
        )
        arena_ranking_model = []
        for ranking, template_name in rankings:
            arena_ranking_model.append(ArenaRanking(
                template_name=template_name,
                model_name=ranking.model_name,
                elo_rating=ranking.elo_rating
            ))
        response.append(ArenaRankingAll(
            challenge_details=challenge_details_model,
            arena_ranking=arena_ranking_model
        ))
    return response


def get_challenge_details_dict(db: db_dependency):
    try:
        challenges = db.query(ArenaChallenge).all()
        challenge_details_dict = {}
        for challenge in challenges:
            challenge_details_dict[challenge.id] = {
                "challenge_name": challenge.challenge_name,
                "text": challenge.text,
                "from_language": challenge.from_language,
                "to_language": challenge.to_language
            }
        return challenge_details_dict

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_ranking_by_challenge_id(arena_ranking_all: List[EloRatingByModelAndTemplate]):
    ranking_by_challenge_id = {}
    for arena_ranking in arena_ranking_all:
        if arena_ranking.challenge_id not in ranking_by_challenge_id:
            ranking_by_challenge_id[arena_ranking.challenge_id] = []
        ranking_by_challenge_id[arena_ranking.challenge_id].append(arena_ranking)
    return ranking_by_challenge_id

def get_ranking_by_challenge_id_with_template_names(arena_ranking_all):
    ranking_by_challenge_id = {}
    for arena_ranking, template_name in arena_ranking_all:
        if arena_ranking.challenge_id not in ranking_by_challenge_id:
            ranking_by_challenge_id[arena_ranking.challenge_id] = []
        # Create a tuple with the rating and template name
        ranking_by_challenge_id[arena_ranking.challenge_id].append((arena_ranking, template_name))
    return ranking_by_challenge_id