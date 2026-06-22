FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY bot /app/bot
RUN pip install --no-cache-dir -e .

CMD ["python", "-m", "bot"]
