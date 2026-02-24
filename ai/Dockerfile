FROM python:3.11-slim

# Prevents Python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1
# Ensures logs show immediately
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (layer caching)
# Add build-essential for compiling native extensions (chroma, etc.)
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 10001 appuser

COPY requirements.txt .
# Use BuildKit cache mount to speed up pip installs
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Copy app code
COPY --chown=appuser:appuser . .

EXPOSE 8002

USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
