FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    ca-certificates \
    libnss3 \
    libatk-bridge2.0-0 \
    libxkbcommon0 \
    libgtk-3-0 \
    libasound2 \
    libgbm1 \
    libxshmfence1 \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/packages/shared/python /workspace/backend/packages/shared/python
COPY backend/worker/requirements.txt /workspace/backend/worker/requirements.txt

RUN pip install --upgrade pip && \
    pip install -r /workspace/backend/worker/requirements.txt && \
    playwright install --with-deps chromium

COPY . /workspace
