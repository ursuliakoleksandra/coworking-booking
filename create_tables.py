import asyncio
import sys

if sys.platform == "win32":
    # asyncpg нестабільно працює зі стандартним ProactorEventLoop на
    # Windows при прямому підключенні з хоста до Postgres у Docker.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.database import Base, engine  # noqa: E402
from app.models import Booking, Room, User, UserRole  # noqa: E402, F401


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")


if __name__ == "__main__":
    asyncio.run(main())
