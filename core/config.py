"""
ReportLens Merkezi Yapılandırma Modülü.
Tüm ayarlar tek noktadan yönetilir. Ortam değişkenleri ile geçersiz kılınabilir.
"""
import os
from pathlib import Path


class Config:
    """Merkezi yapılandırma sınıfı."""

    # Temel dizinler
    BASE_DIR = Path(__file__).parent.parent
    RAW_DATA_DIR = BASE_DIR / "Data" / "raw_data"
    PROCESSED_DATA_DIR = BASE_DIR / "Data" / "processed"
    VECTOR_DB_DIR = BASE_DIR / "Data" / "vector_db"
    IMAGES_DIR = PROCESSED_DATA_DIR / "images"

    # Ollama yapılandırması
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Model yapılandırması
    MODEL_ID = os.getenv("MODEL_ID", "llama3.1:8b")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

    # Qdrant yapılandırması
    QDRANT_URL = os.getenv("QDRANT_URL", None)  # None = yerel dosya modu
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "reportlens_reports")

    # Vektör arama yapılandırması
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
    SEARCH_K = int(os.getenv("SEARCH_K", "8"))

    # Model parametreleri
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
    NUM_CTX = int(os.getenv("NUM_CTX", "32768"))

    @classmethod
    def ensure_directories(cls):
        """Gerekli dizinleri oluşturur."""
        cls.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
        cls.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
