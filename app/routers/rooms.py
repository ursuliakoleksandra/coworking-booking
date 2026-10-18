import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.booking import Booking, BookingStatus
from app.models.room import Room
from app.models.user import User
from app.schemas.room import BusySlot, RoomCreate, RoomRead

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("/", response_model=list[RoomRead])
async def list_rooms(db: AsyncSession = Depends(get_db)) -> list[Room]:
    result = await db.execute(select(Room).order_by(Room.name))
    return list(result.scalars().all())


@router.post("/", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
async def create_room(
    payload: RoomCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> Room:
    """Додати зал або робоче місце — лише адміністратор."""
    room = Room(**payload.model_dump())
    db.add(room)
    await db.commit()
    await db.refresh(room)
    return room


@router.get("/{room_id}", response_model=RoomRead)
async def get_room(room_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Room:
    room = await db.get(Room, room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Ресурс не знайдено")
    return room


@router.get("/{room_id}/availability", response_model=list[BusySlot])
async def room_availability(
    room_id: uuid.UUID,
    start: datetime,
    end: datetime,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Booking]:
    """Зайняті інтервали ресурсу в проміжку [start, end] — для шкали в інтерфейсі."""
    if end <= start:
        raise HTTPException(status_code=422, detail="end має бути пізніше за start")
    if await db.get(Room, room_id) is None:
        raise HTTPException(status_code=404, detail="Ресурс не знайдено")

    query = (
        select(Booking)
        .where(
            Booking.room_id == room_id,
            Booking.status != BookingStatus.CANCELLED,
            Booking.start_time < end,
            Booking.end_time > start,
        )
        .order_by(Booking.start_time)
    )
    return list((await db.execute(query)).scalars().all())
