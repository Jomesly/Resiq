FROM python:3.12-slim AS common
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HOME=/home/resiq
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml constraints.txt ./
# Cache dependencies and weights independently of application source edits.
RUN mkdir app && touch app/__init__.py
RUN pip install -c constraints.txt '.[s3]'
COPY alembic.ini ./
COPY migrations ./migrations
RUN useradd --create-home --uid 10001 resiq && mkdir -p /data && chown -R resiq:resiq /data /app
USER resiq
ENV STORAGE_ROOT=/data
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--limit-concurrency", "100", "--timeout-keep-alive", "5"]

FROM common AS dependencies

FROM dependencies AS paddle-dependencies
USER root
RUN pip install -c constraints.txt '.[paddle]'
USER resiq
# Cache model weights at build time; startup must not depend on model host availability.
COPY app/config.py app/config.py
COPY app/schemas.py app/schemas.py
COPY app/vision app/vision
RUN python -c "from app.config import Settings; from app.vision.ocr import create_engine; create_engine(Settings(ocr_engine='paddle'))"

FROM dependencies AS base
COPY --chown=resiq:resiq app ./app

FROM paddle-dependencies AS paddle
COPY --chown=resiq:resiq app ./app
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
