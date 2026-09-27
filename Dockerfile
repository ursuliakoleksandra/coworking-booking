FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY app/ ./app/
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY pyproject.toml .flake8 create_tables.py ./

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
