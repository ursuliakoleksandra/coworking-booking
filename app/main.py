from fastapi import FastAPI

from app.core.config import settings
from app.routers import auth, bookings, health, home, rooms

app = FastAPI(title=settings.app_name)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(rooms.router)
app.include_router(bookings.router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": settings.app_name}
