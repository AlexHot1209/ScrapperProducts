FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/packages/shared/python /workspace/backend/packages/shared/python
COPY backend/api/requirements.txt /workspace/backend/api/requirements.txt

RUN pip install --upgrade pip && \
    pip install -r /workspace/backend/api/requirements.txt

COPY . /workspace

EXPOSE 8000
