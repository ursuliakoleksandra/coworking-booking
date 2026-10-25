#!/bin/sh
set -e

echo "[entrypoint] створення таблиць у БД (якщо їх ще немає)..."
python create_tables.py

if [ -n "${BOOTSTRAP_ADMIN_EMAIL:-}" ] && [ -n "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then
    python scripts/create_admin.py "$BOOTSTRAP_ADMIN_EMAIL" "${BOOTSTRAP_ADMIN_NAME:-Administrator}" "$BOOTSTRAP_ADMIN_PASSWORD"
fi

echo "[entrypoint] запуск: $*"
exec "$@"
