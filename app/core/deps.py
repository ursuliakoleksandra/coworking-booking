from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, UserRole

# tokenUrl вказує Swagger UI, куди слати логін-форму для кнопки "Authorize"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Дістає поточного користувача з JWT-токена.

    Кидає 401, якщо токен відсутній, невалідний, протермінований, або
    користувача більше не існує в БД — саме це покриває сценарій
    "анонімний доступ до захищеного маршруту".
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не вдалося перевірити облікові дані",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_access_token(token)
    if user_id is None:
        raise credentials_exception

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_role(*allowed_roles: UserRole):
    """Фабрика залежностей для вертикального розмежування прав за роллю.

    Використання: Depends(require_role(UserRole.ADMIN)) — поверне 403,
    якщо роль поточного користувача не входить у allowed_roles.
    """

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостатньо прав для доступу до цього ресурсу",
            )
        return current_user

    return role_checker


require_admin = require_role(UserRole.ADMIN)
