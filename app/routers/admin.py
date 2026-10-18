from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.deps import require_admin
from app.models.booking import Booking
from app.models.user import User
from app.schemas.booking import AdminBookingRead
from app.schemas.user import UserRead

# Усі маршрути цього роутера доступні лише ролі ADMIN (інакше 401/403).
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/users", response_model=list[UserRead])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[User]:
    result = await db.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


@router.get("/bookings", response_model=list[AdminBookingRead])
async def list_all_bookings(db: AsyncSession = Depends(get_db)) -> list[AdminBookingRead]:
    query = (
        select(Booking)
        .options(selectinload(Booking.user), selectinload(Booking.room))
        .order_by(Booking.start_time.desc())
    )
    bookings = (await db.execute(query)).scalars().all()
    return [
        AdminBookingRead(
            id=b.id,
            room_id=b.room_id,
            user_id=b.user_id,
            start_time=b.start_time,
            end_time=b.end_time,
            status=b.status,
            user_email=b.user.email,
            room_name=b.room.name,
        )
        for b in bookings
    ]
