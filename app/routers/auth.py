from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, UserRole
from app.schemas.user import Token, UserRead, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)) -> User:
    """Самостійна реєстрація. Завжди створює користувача з роллю USER.

    Реєстрація адміністраторів навмисно не публічна (як і вказано в
    завданні як опціональна) — адмінів створює вже наявний адмін, або їх
    заводять напряму через скрипт `scripts/create_admin.py`.
    """
    existing = (
        await db.execute(select(User).where(User.email == payload.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Користувач з такою поштою вже зареєстрований",
        )

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=UserRole.USER,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Вхід для будь-якого типу користувача (і USER, і ADMIN) — за email/паролем.

    OAuth2PasswordRequestForm — стандартна форма FastAPI (поля username,
    password); ми кладемо в 'username' саме email. Це дозволяє одразу
    користуватись кнопкою "Authorize" у Swagger UI.
    """
    user = (
        await db.execute(select(User).where(User.email == form_data.username))
    ).scalar_one_or_none()

    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неправильний email або пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Обліковий запис деактивовано",
        )

    access_token = create_access_token(subject=user.id)
    return Token(access_token=access_token, role=user.role)


@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """Повертає дані поточного автентифікованого користувача."""
    return current_user
