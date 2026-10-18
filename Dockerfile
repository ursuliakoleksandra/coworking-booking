FROM python:3.12-slim

ARG REQUIREMENTS=requirements.txt
ENV PYTHONPATH=/app PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r ${REQUIREMENTS}

COPY app/ ./app/
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY pyproject.toml .flake8 create_tables.py ./

RUN adduser --disabled-password --gecos "" --no-create-home appuser
USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
