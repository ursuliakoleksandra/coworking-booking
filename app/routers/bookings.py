import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.booking import Booking, BookingStatus
from app.schemas.booking import BookingCreate, BookingRead

router = APIRouter(prefix="/bookings", tags=["bookings"])

# TODO (наступні лабораторні): винести перевірку/лок у Redis
# (SETNX room:{room_id}:{slot} з TTL) — щоб не тримати блокування на рівні
# БД довше, ніж потрібно, і витримати пікове навантаження на початку
# місяця/тижня.


@router.post("/", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreate,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Booking:
    """Створює бронювання, перевіряючи перетин часових слотів для ресурсу.

    Це і є "вузьке місце" конкурентного доступу: якщо два запити
    одночасно пройдуть перевірку нижче до того, як перший зробить commit,
    можливе подвійне бронювання. Це навмисно залишено як точка для
    вдосконалення (advisory lock / Redis lock) у наступних лабораторних.
    """
    overlap_query = select(Booking).where(
        Booking.room_id == payload.room_id,
        Booking.status != BookingStatus.CANCELLED,
        Booking.start_time < payload.end_time,
        Booking.end_time > payload.start_time,
    )
    existing = (await db.execute(overlap_query)).scalars().first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Обраний слот вже заброньовано",
        )

    booking = Booking(
        room_id=payload.room_id,
        user_id=user_id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status=BookingStatus.CONFIRMED,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking
