FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HOME=/home/resiq
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml constraints.txt ./
COPY app ./app
RUN pip install -c constraints.txt '.[s3]'
COPY alembic.ini ./
COPY migrations ./migrations
RUN useradd --create-home --uid 10001 resiq && mkdir -p /data && chown -R resiq:resiq /data /app
USER resiq
ENV STORAGE_ROOT=/data
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

FROM base AS paddle
USER root
RUN pip install -c constraints.txt '.[paddle]'
USER resiq
# Cache model weights at build time; startup must not depend on model host availability.
RUN python -c "from app.config import Settings; from app.vision.ocr import create_engine; create_engine(Settings(ocr_engine='paddle'))"
