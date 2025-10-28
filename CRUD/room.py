from database import get_db
from typing import Annotated, List, Dict, Any
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from models.room import Room
from models.arena_rating import BattleResult
import logging

db_dependency = Annotated[Session, Depends(get_db)]

logger = logging.getLogger(__name__)

def get_or_create_room(db: db_dependency, room_id: str | None, user_id: str | None = None) -> str:
    """
    Get existing room or create a new one.
    
    Args:
        db: Database session
        room_id: Optional existing room ID
        user_id: Optional user ID for room creation
    
    Returns:
        str: Room ID (existing or newly created)
    """

    print(f"room_id::::: {room_id}")
    print(f"user_id:::: {user_id}")
    if room_id:
        # Verify room exists
        try:
            import uuid as uuid_lib
            room_uuid = uuid_lib.UUID(room_id)
            room = db.query(Room).filter(Room.id == room_uuid).first()
            if room:
                return str(room.id)
        except (ValueError, Exception) as e:
            logger.warning(f"Invalid room_id provided: {room_id}, creating new room. Error: {e}")
    
    # Create new room
    try:
        new_room = Room(
            user_id=user_id if user_id else "anonymous"
        )
        db.add(new_room)
        db.commit()
        db.refresh(new_room)
        return str(new_room.id)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating room: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating room: {str(e)}")

def get_chat_history(db: db_dependency, user_id: str) -> List[Dict[str, Any]]:
    """
    Get chat history for a given user ID.
    Returns list of rooms ordered by last battle time, including the first battle title.
    """
    try:
        # Subquery to get the last battle time for each room
        last_battle_subquery = (
            db.query(
                BattleResult.room_id,
                func.max(BattleResult.updated_at).label('last_battle_time')
            )
            .group_by(BattleResult.room_id)
            .subquery()
        )
        
        # Subquery to get the first battle title for each room
        first_battle_subquery = (
            db.query(
                BattleResult.room_id,
                BattleResult.input_text.label('title')
            )
            .distinct(BattleResult.room_id)
            .order_by(BattleResult.room_id, BattleResult.created_at.asc())
            .subquery()
        )
        
        # Main query: join rooms with battle info and order by last battle time
        rooms = (
            db.query(
                Room,
                first_battle_subquery.c.title,
                last_battle_subquery.c.last_battle_time
            )
            .outerjoin(last_battle_subquery, Room.id == last_battle_subquery.c.room_id)
            .outerjoin(first_battle_subquery, Room.id == first_battle_subquery.c.room_id)
            .filter(Room.user_id == user_id)
            .order_by(last_battle_subquery.c.last_battle_time.desc().nulls_last())
            .all()
        )
        
        # Format the result
        result = []
        for room, title, last_battle_time in rooms:
            result.append({
                "id": str(room.id),
                "user_id": room.user_id,
                "created_at": room.created_at,
                "updated_at": room.updated_at,
                "title": title or "Untitled",
                "last_battle_time": last_battle_time
            })
        
        return result
    except Exception as e:
        logger.error(f"Error fetching chat history for user {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching chat history: {str(e)}")

def get_battle_results_by_room_id(db: db_dependency, room_id: str) -> List[BattleResult]:
    """
    Get all battle results for a given room ID.
    """
    try:
        import uuid as uuid_lib
        room_uuid = uuid_lib.UUID(room_id)
        
        # Verify room exists
        room = db.query(Room).filter(Room.id == room_uuid).first()
        if not room:
            raise HTTPException(status_code=404, detail=f"Room with id {room_id} not found")
        
        # Query all battle results for this room
        battle_results = db.query(BattleResult).filter(BattleResult.room_id == room_uuid).all()
        
        return battle_results
    
    except ValueError:
        logger.error(f"Invalid UUID format for room_id: {room_id}")
        raise HTTPException(status_code=400, detail=f"Invalid room_id format: {room_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching battle results for room {room_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching battle results: {str(e)}")