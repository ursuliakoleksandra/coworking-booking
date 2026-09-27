from fastapi import APIRouter, Depends

from app.core.deps import get_current_user, require_admin
from app.models.user import User

router = APIRouter(prefix="/home", tags=["home"])


@router.get("/user")
async def user_home(current_user: User = Depends(get_current_user)) -> dict:
    """Домашня сторінка звичайного користувача.

    Доступна будь-якому автентифікованому користувачу (USER чи ADMIN).
    Анонімний запит поверне 401 (спрацює get_current_user).
    """
    return {
        "message": f"Вітаємо, {current_user.full_name}!",
        "role": current_user.role,
        "sections": ["Мої бронювання", "Пошук залів", "Профіль"],
    }


@router.get("/admin")
async def admin_home(current_user: User = Depends(require_admin)) -> dict:
    """Адмін-панель — заглушка.

    Доступна лише користувачам з роллю ADMIN. Звичайний користувач
    отримає 403 Forbidden (вертикальне розмежування ролей) — саме цей
    сценарій вимагає завдання лабораторної.
    """
    return {
        "message": f"Адмін-панель, {current_user.full_name}",
        "sections": ["Усі бронювання", "Управління залами", "Управління користувачами"],
    }
