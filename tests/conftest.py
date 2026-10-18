from collections.abc import AsyncGenerator, Callable, Coroutine

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.user import User, UserRole

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async with session_maker() as session:
        yield session

    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def make_user(
    db_session: AsyncSession,
) -> Callable[..., Coroutine[None, None, User]]:

    async def _make_user(
        email: str,
        password: str,
        role: UserRole = UserRole.USER,
        full_name: str = "Test User",
    ) -> User:
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=role,
        )
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        return user

    return _make_user


@pytest.fixture
async def auth_headers(
    client: AsyncClient,
) -> Callable[[str, str], Coroutine[None, None, dict[str, str]]]:

    async def _auth_headers(email: str, password: str) -> dict[str, str]:
        response = await client.post("/auth/login", data={"username": email, "password": password})
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _auth_headers
