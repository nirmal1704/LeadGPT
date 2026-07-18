FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install firefox --with-deps

RUN camoufox fetch

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

RUN mkdir -p /opt/extensions && \
    curl -L "https://github.com/NopeCHALLC/nopecha-extension/releases/latest/download/nopecha.crx" \
    -o /opt/extensions/nopecha.crx

RUN mkdir -p /tmp/exports

COPY . .
