FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1
ENV DBUS_SESSION_BUS_ADDRESS=/dev/null

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libdbus-1-3 libxkbcommon0 libx11-xcb1 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2 \
    libgtk-3-0 dbus-x11 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install CPU-only PyTorch to prevent massive 5GB+ CUDA downloads which cause 'out of space' errors
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install firefox

RUN camoufox fetch

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

RUN mkdir -p /opt/extensions && \
    curl -L "https://github.com/NopeCHALLC/nopecha-extension/releases/latest/download/nopecha.crx" \
    -o /opt/extensions/nopecha.crx

RUN mkdir -p /tmp/exports

COPY . .
