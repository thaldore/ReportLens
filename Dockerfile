# Python 3.10 tabanlı resmi imajı kullan
FROM python:3.10-slim

# Çalışma dizinini ayarla
WORKDIR /app

# Gerekli sistem kütüphanelerini kur (PDF işleme ve tablo çıkarma için)
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları kopyala ve kur
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# Streamlit için portu aç
EXPOSE 8501

# Uygulamayı başlat
CMD ["streamlit", "run", "ui/main.py", "--server.port=8501", "--server.address=0.0.0.0"]
