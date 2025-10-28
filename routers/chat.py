from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from typing import Annotated, List, Optional
import logging

from models.room import Room
from models.arena_rating import BattleResult
from schemas.chat import RoomResponse, RoomDetailResponse, BattleResultResponse
from CRUD.room import get_battle_results_by_room_id, get_chat_history as get_chat_history_crud

logger = logging.getLogger(__name__)

db_dependency = Annotated[Session, Depends(get_db)]

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/history", response_model=List[RoomResponse], status_code=status.HTTP_200_OK)
def get_chat_history(
    db: db_dependency,
    user_id: Optional[str] = Query(None, description="Filter by user ID")
):
    """
    Get chat history - list of all rooms with battle counts.
    """
    chat_history = get_chat_history_crud(db, user_id)
    return chat_history


@router.get("/{room_id}", response_model=RoomDetailResponse, status_code=status.HTTP_200_OK)
def get_chat_detail(db: db_dependency, room_id: str):
    """
    Get chat detail for a specific room including all battle results.
    """
    try:
        import uuid as uuid_lib
        room_uuid = uuid_lib.UUID(room_id)
        
        # Get the room
        room = db.query(Room).filter(Room.id == room_uuid).first()
        if not room:
            raise HTTPException(status_code=404, detail=f"Room with id {room_id} not found")
        
        # Get all battle results for this room using the CRUD function
        battle_results = get_battle_results_by_room_id(db, room_id)
        
        # Convert battle results to response schema
        battle_result_responses = [
            BattleResultResponse(
                id=str(battle.id),
                template_A_id=battle.template_A_id,
                template_B_id=battle.template_B_id,
                input_text=battle.input_text,
                output_text_A=battle.output_text_A,
                output_text_B=battle.output_text_B,
                model_A=battle.model_A,
                model_B=battle.model_B,
                challenge_id=battle.challenge_id,
                winner_status=battle.winner_status,
                created_at=battle.created_at,
                updated_at=battle.updated_at
            )
            for battle in battle_results
        ]
        
        # Create and return room detail response
        return RoomDetailResponse(
            id=str(room.id),
            user_id=room.user_id,
            created_at=room.created_at,
            updated_at=room.updated_at,
            battle_results=battle_result_responses
        )
    
    except ValueError:
        logger.error(f"Invalid UUID format for room_id: {room_id}")
        raise HTTPException(status_code=400, detail=f"Invalid room_id format: {room_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching chat detail for room {room_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching chat detail: {str(e)}")

