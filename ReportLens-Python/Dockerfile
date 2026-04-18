# ══════════════════════════════════════════════════════════════════
# ReportLens Python App — Docker Image
# FastAPI + Core Engine + Frontend (HTML/CSS/JS)
# ══════════════════════════════════════════════════════════════════

FROM python:3.10-slim

WORKDIR /app
ENV PYTHONPATH=/app

# ── Sistem Bağımlılıkları (PDF, OCR, MSSQL Driver) ────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-tur \
    tesseract-ocr-eng \
    curl \
    dos2unix \
    gnupg2 \
    unixodbc-dev \
    ca-certificates \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64,arm64,armhf signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

# ── Python Bağımlılıkları ──────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --retries 10 -r requirements.txt

# ── Proje Dosyaları ────────────────────────────────────────────────
COPY . .

# Entrypoint scriptini hazırla
RUN dos2unix scripts/docker_entrypoint.sh && chmod +x scripts/docker_entrypoint.sh

# ── FastAPI Portu ──────────────────────────────────────────────────
EXPOSE 8000

# ── Healthcheck ────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8000/api/status || exit 1

# ── Çalıştırma ─────────────────────────────────────────────────────
ENTRYPOINT ["scripts/docker_entrypoint.sh"]
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
