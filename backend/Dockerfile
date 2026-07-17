FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

RUN camoufox fetch

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

RUN mkdir -p /opt/extensions && \
    curl -L "https://github.com/NopeCHALLC/nopecha-extension/releases/latest/download/nopecha.crx" \
    -o /opt/extensions/nopecha.crx

RUN mkdir -p /tmp/exports

COPY . .
