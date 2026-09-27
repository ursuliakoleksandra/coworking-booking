"""Кастомні типи SQLAlchemy, портовані між діалектами БД.

GUID зберігає UUID як нативний PostgreSQL UUID у продакшн-БД, і як
CHAR(32) (hex-рядок без дефісів) на будь-якому іншому діалекті — зокрема
на SQLite, який ми використовуємо для швидких pytest-тестів, щоб не
тримати Postgres піднятим для юніт-тестів.

Патерн офіційно задокументований у SQLAlchemy: "Backend-agnostic GUID Type".
"""

import uuid

from sqlalchemy import CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            value = uuid.UUID(value)
        return value.hex

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)
