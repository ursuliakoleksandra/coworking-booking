"""Одноразовий скрипт для створення адміністратора.

Реєстрація адміністраторів навмисно не публічна (POST /auth/register
завжди створює звичайного користувача) — перший адмін заводиться саме
так, з довіреного середовища (наприклад, всередині Docker-контейнера).

Використання:
    python scripts/create_admin.py admin@example.com "Admin User" secretpass123
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole


async def create_admin(email: str, full_name: str, password: str) -> None:
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if existing is not None:
            print(f"Користувач {email} вже існує (роль: {existing.role}).")
            return

        admin = User(
            email=email,
            full_name=full_name,
            hashed_password=hash_password(password),
            role=UserRole.ADMIN,
        )
        db.add(admin)
        await db.commit()
        print(f"Адміністратора {email} створено.")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print('Використання: python scripts/create_admin.py <email> "<full name>" <password>')
        sys.exit(1)

    asyncio.run(create_admin(sys.argv[1], sys.argv[2], sys.argv[3]))
