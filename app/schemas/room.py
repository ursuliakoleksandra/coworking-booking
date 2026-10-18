import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.room import RoomType


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    room_type: RoomType
    capacity: int = Field(ge=1, le=500)
    location: str = Field(min_length=1, max_length=255)


class RoomRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    room_type: RoomType
    capacity: int
    location: str


class BusySlot(BaseModel):
    """Зайнятий інтервал ресурсу. Без даних про те, хто саме забронював."""

    start_time: datetime
    end_time: datetime
