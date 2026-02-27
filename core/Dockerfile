FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10001 -g 10001 -G 10001 appuser || useradd -m -u 10001 appuser

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt

COPY --chown=appuser:appuser . .

# Collect static files at BUILD TIME (baked into the image)
# Dummy credentials satisfy settings.py validation — nothing actually connects
RUN SECRET_KEY=build-collect-static-dummy-key \
    DB_NAME=dummy DB_USER=dummy DB_PASSWORD=dummy DB_HOST=localhost DB_PORT=5432 \
    CLOUDINARY_CLOUD_NAME=dummy CLOUDINARY_API_KEY=dummy CLOUDINARY_API_SECRET=dummy \
    python manage.py collectstatic --noinput

RUN chown -R appuser:appuser staticfiles

EXPOSE 8000

USER appuser

CMD ["gunicorn", "project.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
