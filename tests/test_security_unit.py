"""Юніт-тести модуля app.core.security.

Жоден із цих тестів не торкається бази даних чи мережі — це чисті
юніт-тести функцій хешування паролів та роботи з JWT.
"""

import uuid

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_returns_different_value_than_plain() -> None:
    hashed = hash_password("super-secret-123")
    assert hashed != "super-secret-123"
    assert len(hashed) > 20


def test_verify_password_correct() -> None:
    hashed = hash_password("super-secret-123")
    assert verify_password("super-secret-123", hashed) is True


def test_verify_password_incorrect() -> None:
    hashed = hash_password("super-secret-123")
    assert verify_password("wrong-password", hashed) is False


def test_hash_password_is_salted() -> None:
    """Той самий пароль має давати різні хеші (унікальна сіль щоразу)."""
    hash_one = hash_password("same-password")
    hash_two = hash_password("same-password")
    assert hash_one != hash_two


def test_create_and_decode_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(subject=user_id)
    decoded_id = decode_access_token(token)
    assert decoded_id == user_id


def test_decode_invalid_token_returns_none() -> None:
    assert decode_access_token("this.is.not-a-valid-jwt") is None


def test_decode_expired_token_returns_none() -> None:
    user_id = uuid.uuid4()
    # Токен, термін дії якого сплив ще до створення - завжди невалідний.
    token = create_access_token(subject=user_id, expires_minutes=-1)
    assert decode_access_token(token) is None
