import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.room import Room

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("/")
async def list_rooms(db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(select(Room))
    rooms = result.scalars().all()
    return [
        {
            "id": str(room.id),
            "name": room.name,
            "type": room.room_type,
            "capacity": room.capacity,
            "location": room.location,
        }
        for room in rooms
    ]


@router.get("/{room_id}")
async def get_room(room_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> dict:
    room = await db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Ресурс не знайдено")
    return {
        "id": str(room.id),
        "name": room.name,
        "type": room.room_type,
        "capacity": room.capacity,
        "location": room.location,
    }
