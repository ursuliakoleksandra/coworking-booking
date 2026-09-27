import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.booking import Booking, BookingStatus
from app.models.user import User, UserRole
from app.schemas.booking import BookingCreate, BookingRead

router = APIRouter(prefix="/bookings", tags=["bookings"])

# TODO (наступні лабораторні): винести перевірку/лок у Redis
# (SETNX room:{room_id}:{slot} з TTL) — щоб не тримати блокування на рівні
# БД довше, ніж потрібно, і витримати пікове навантаження на початку
# місяця/тижня.


async def _get_owned_or_404(booking_id: uuid.UUID, current_user: User, db: AsyncSession) -> Booking:
    """Дістає бронювання за id і перевіряє права доступу до нього.

    Горизонтальне розмежування прав (IDOR): звичайний користувач може
    працювати лише зі своїм бронюванням (403 на чуже), адміністратор —
    з будь-яким.
    """
    booking = await db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Бронювання не знайдено")

    if current_user.role != UserRole.ADMIN and booking.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ви не маєте доступу до чужого бронювання",
        )
    return booking


@router.post("/", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Booking:
    """Створює бронювання від імені поточного автентифікованого користувача.

    user_id більше не приймається з тіла запиту (раніше це давало б будь-
    якому користувачу створювати бронювання від чужого імені) — він
    завжди береться з JWT-токена.

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
        user_id=current_user.id,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status=BookingStatus.CONFIRMED,
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking


@router.get("/my", response_model=list[BookingRead])
async def list_my_bookings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Booking]:
    """Список бронювань поточного користувача (тільки власні)."""
    result = await db.execute(select(Booking).where(Booking.user_id == current_user.id))
    return list(result.scalars().all())


@router.get("/{booking_id}", response_model=BookingRead)
async def get_booking(
    booking_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Booking:
    """Перегляд одного бронювання — лише власник або адміністратор."""
    return await _get_owned_or_404(booking_id, current_user, db)


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking(
    booking_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Скасування бронювання — лише власник або адміністратор.

    Спроба скасувати чуже бронювання поверне 403 Forbidden — саме цей
    сценарій (IDOR) вимагає завдання лабораторної.
    """
    booking = await _get_owned_or_404(booking_id, current_user, db)
    booking.status = BookingStatus.CANCELLED
    await db.commit()
