import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    room_id: uuid.UUID
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def check_time_order(self) -> "BookingCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time має бути пізніше за start_time")
        return self


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    room_id: uuid.UUID
    user_id: uuid.UUID
    start_time: datetime
    end_time: datetime
    status: BookingStatus
