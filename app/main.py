from fastapi import FastAPI

from app.core.config import settings
from app.routers import bookings, health, rooms

app = FastAPI(title=settings.app_name)

app.include_router(health.router)
app.include_router(rooms.router)
app.include_router(bookings.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": settings.app_name}
