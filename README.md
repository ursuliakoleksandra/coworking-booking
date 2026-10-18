# Слот — платформа бронювання коворкінгів та конференц-залів

![CI](https://github.com/ursuliakoleksandra/coworking-booking/actions/workflows/ci.yml/badge.svg)

Навчальний проєкт: FastAPI + PostgreSQL + Redis + Docker, веб-інтерфейс без збірки.

- ЛР №1 — архітектура, каркас, контроль якості коду (black, ruff, flake8, pre-commit)
- ЛР №2 — користувачі, ролі `USER`/`ADMIN`, JWT, розмежування прав, тести
- ЛР №3 — розділення sandbox/production, ізоляція БД, режими безпеки, CI/CD; веб-інтерфейс

## 1. Предметна область

Платформа бронювання коворкінгів та конференц-залів. Домен дає пікові навантаження
(початок місяця/тижня) і конкурентний доступ до одного ресурсу (двоє людей одночасно
бронюють одну залу) — це основа для наступних тем курсу: кешування, блокування, масштабування.

## 2. Архітектура

Схема — `docs/architecture.svg`: клієнти → балансувальник → кілька інстансів FastAPI →
Redis (кеш і блокування слотів) + PostgreSQL. Зеленим позначено реалізоване, фіолетовим —
заплановане (черга повідомлень, read-репліка).

## 3. Користувачі та права (ЛР №2)

- JWT замість серверних сесій: кілька інстансів API за балансувальником не потребують спільного сховища сесій.
- Паролі — лише bcrypt-хеші. Публічна реєстрація завжди створює `USER`; адміністраторів
  заводить `scripts/create_admin.py`.
- Вертикальне розмежування — `require_role(...)` (`/home/admin`, `/admin/*`, створення залів — лише `ADMIN`).
- Горизонтальне (IDOR) — чуже бронювання повертає 403; `user_id` береться з токена, а не з запиту.

## 4. Середовища: sandbox і production (ЛР №3)

| | sandbox | production |
|---|---|---|
| Призначення | розробка, демо, тестування | робоче середовище |
| Файл змінних | `.env.sandbox` | `.env.production` |
| `DEBUG` | `true` (детальні помилки) | `false` |
| Swagger `/docs` | увімкнено | вимкнено (`ENABLE_DOCS=false`) |
| База даних | `booking_sandbox` | `booking_production` |
| Порти (застосунок / Postgres / Redis) | 8000 / 5432 / 6379 | 8001 / 5433 / 6380 |
| Контейнери й том з даними | проєкт `coworking-sandbox` | проєкт `coworking-production` |
| Залежності в образі | `requirements-dev.txt` | `requirements.txt` |

### Як працює конфігурація

У коді немає жодних паролів, ключів чи рядків підключення. Усе читає `app/core/config.py`
(pydantic-settings) зі змінних оточення. Файл `.env.<APP_ENV>` використовується для локального
запуску; змінні, задані системою (Docker, хостинг), мають пріоритет над файлом.

- `SECRET_KEY` і доступи до БД не мають значень за замовчуванням: без них застосунок не стартує.
- Реальні `.env.sandbox` та `.env.production` у `.gitignore`. У git лежать лише шаблони
  `.env.sandbox.example` і `.env.production.example`. Файли `.env*` також виключені з Docker-образу.
- Захисні перевірки при старті (застосунок відмовляється запускатись, якщо):
  - production із `DEBUG=true`;
  - production із ключем чи паролем-заглушкою (`CHANGE-ME…`);
  - `SECRET_KEY` коротший за 32 символи;
  - production підключений до бази зі `sandbox`/`test` у назві, а sandbox — до бази з `prod`.

### Ізоляція баз даних

Кожне середовище — окремий Docker-проєкт (`-p`): власний контейнер Postgres, власний том,
власна база, окремі облікові дані та порт. Тестові дані фізично не можуть потрапити в
production. Автотести взагалі не торкаються жодної з них (SQLite у пам'яті).

## 5. Запуск

### 5.1. Підготовка (один раз)

```powershell
git clone https://github.com/ursuliakoleksandra/coworking-booking.git
cd coworking-booking
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

### 5.2. Sandbox

```powershell
copy .env.sandbox.example .env.sandbox
docker compose --env-file .env.sandbox -p coworking-sandbox -f config/docker-compose.yml up -d --build
docker compose --env-file .env.sandbox -p coworking-sandbox -f config/docker-compose.yml exec app python create_tables.py
docker compose --env-file .env.sandbox -p coworking-sandbox -f config/docker-compose.yml exec app python scripts/create_admin.py admin@example.com "Admin User" secretpass123
```

Відкрийте http://localhost:8000 (інтерфейс) або http://localhost:8000/docs (Swagger).
Перевірка середовища: http://localhost:8000/health → `"environment": "sandbox"`.

### 5.3. Production

```powershell
copy .env.production.example .env.production
```

Відкрийте `.env.production` і замініть усі `CHANGE-ME` (ключ: `python -c "import secrets; print(secrets.token_urlsafe(48))"`). Далі:

```powershell
docker compose --env-file .env.production -p coworking-production -f config/docker-compose.yml up -d --build
docker compose --env-file .env.production -p coworking-production -f config/docker-compose.yml exec app python create_tables.py
docker compose --env-file .env.production -p coworking-production -f config/docker-compose.yml exec app python scripts/create_admin.py admin@yourcompany.com "Admin" <надійний-пароль>
```

Інтерфейс: http://localhost:8001, `/health` → `"environment": "production"`, `/docs` повертає 404.

Обидва середовища можна тримати запущеними одночасно — порти й дані в них різні.

### 5.4. Зупинка

```powershell
docker compose --env-file .env.sandbox -p coworking-sandbox -f config/docker-compose.yml down
```

Додайте `-v`, щоб видалити й дані бази цього середовища.

## 6. Безпечна обробка помилок

- `DEBUG=false` (production): при будь-якій неочікуваній помилці користувач бачить лише
  `{"detail": "Внутрішня помилка сервера…", "error_id": "a1b2c3d4"}`. Стектрейс іде тільки в
  серверний лог разом із тим самим `error_id`, тож помилку можна знайти за кодом.
- `DEBUG=true` (sandbox): показується детальний трейсбек для розробника.
- Усі відповіді мають заголовки `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`.
- Інтерфейс вставляє дані сервера лише як текст (без `innerHTML`) — захист від XSS.

## 7. Веб-інтерфейс

Віддається самим FastAPI (`app/static`, без збірки): `/` — вхід і реєстрація.

- **Користувач:** вибір залу, шкала дня 08:00–20:00 із зайнятими інтервалами, бронювання,
  «Мої бронювання» зі скасуванням.
- **Адміністратор:** додатково — усі бронювання (з іменами користувачів), додавання залів, список користувачів.

Права перевіряє сервер (інтерфейс лише приховує зайве), тож 401/403 повертаються й на прямі запити до API.

## 8. CI/CD (GitHub Actions)

`.github/workflows/ci.yml` запускається при кожному Pull Request і коміті в `main`:

1. **Лінтери і тести:** `black --check`, `ruff`, `flake8`, `pytest` (юніт- та інтеграційні тести з ЛР №2 + нові).
2. **Збірка production-образу:** `docker build` лише з робочими залежностями — перевіряє, що образ збирається.

Тести виставляють власне середовище (`APP_ENV=test`, `tests/__init__.py`), тому CI не потребує секретів.

## 9. Тести

```powershell
python -m pytest -v
```

Docker і Postgres не потрібні. Покрито: автентифікацію та ролі, IDOR, конфігурації
(`tests/test_config.py`), безпечні помилки 500 (`tests/test_error_handling.py`),
інтерфейс і адмін-API (`tests/test_ui_and_admin.py`).

## 10. Контроль якості коду

black, ruff, flake8 + pre-commit (`pre-commit install`) блокують коміт із помилками стилю;
додатково `detect-private-key` блокує випадковий коміт приватних ключів. Приклади: `docs/precommit-demo*.md`.

## 11. Структура

```
app/
  core/        config (середовища), database, security, deps (RBAC), types
  models/ schemas/ routers/ (auth, home, admin, rooms, bookings, health)
  static/      веб-інтерфейс (index.html, app.js, style.css)
config/        docker-compose.yml (спільний для обох середовищ)
.github/workflows/ci.yml
.env.sandbox.example  .env.production.example
scripts/       create_admin.py
tests/
```

