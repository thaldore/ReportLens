# Python 3.10 tabanlı resmi imaj
FROM python:3.10-slim

# Çalışma dizini
WORKDIR /app
ENV PYTHONPATH=/app

# Gerekli sistem kütüphaneleri (PDF, OCR, curl, dos2unix)
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



# Bağımlılıkları kopyala ve kur
COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --retries 10 -r requirements.txt



# Proje dosyalarını kopyala
COPY . .

# Entrypoint scriptini Unix formatına çevir ve çalıştırma izni ver
RUN dos2unix scripts/docker_entrypoint.sh && chmod +x scripts/docker_entrypoint.sh

# Streamlit portu
EXPOSE 8501

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8501/_stcore/health || exit 1

# Entrypoint: Ollama'yı bekle, modelleri indir, uygulamayı başlat
ENTRYPOINT ["scripts/docker_entrypoint.sh"]
CMD ["streamlit", "run", "ui/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
