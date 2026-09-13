import uuid
from enum import Enum as PyEnum

from sqlalchemy import Enum, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RoomType(str, PyEnum):
    COWORKING_DESK = "coworking_desk"
    CONFERENCE_ROOM = "conference_room"


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    room_type: Mapped[RoomType] = mapped_column(Enum(RoomType), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=1)
    location: Mapped[str] = mapped_column(String(255), nullable=False)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="room")
