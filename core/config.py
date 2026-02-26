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
    
    # Maksimum bağlam limiti (8b model güvenli sınırı)
    MAX_CONTEXT_CHUNKS = 40 

    # Model parametreleri
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
    NUM_CTX = int(os.getenv("NUM_CTX", "32768"))

    # YÖKAK Rubrik Kriterleri (Standart)
    RUBRIC_CRITERIA = {
        "A. Liderlik, Yönetişim ve Kalite": (
            "Misyon, vizyon, stratejik amaçlar, yönetim sistemleri, "
            "paydaş katılımı ve uluslararasılaşma süreçleri."
        ),
        "B. Eğitim ve Öğretim": (
            "Programların tasarımı, yürütülmesi, öğrenme kaynakları, "
            "öğretim kadrosu ve programların izlenmesi."
        ),
        "C. Araştırma ve Geliştirme": (
            "Araştırma stratejisi, kaynakları, yetkinliği ve performansı."
        ),
        "D. Toplumsal Katkı": (
            "Toplumsal katkı stratejisi, kaynakları ve performansı."
        )
    }

    # Puanlama Skalası (YÖKAK uyumlu — rubric_evaluator.py ile hizalı)
    RUBRIC_SCORING_KEY = {
        1: "Hiç Yok: İlgili konuda hiçbir planlama veya uygulama örneği yok.",
        2: "Planlama/Niyet: Konuyla ilgili niyet veya plan var, somut uygulama yok.",
        3: "Uygulama: En az bir somut uygulama örneği veya tablo verisi mevcut.",
        4: "İzleme: Uygulama yapılmış ve sonuçları düzenli takip ediliyor/raporlanıyor.",
        5: "Sürekli İyileştirme: PUKÖ döngüsü tamamlanmış; izleme verilerine göre iyileştirmeler yapılmış.",
    }

    # Birim adı → arama anahtar kelimeleri eşleşmesi (RAG filtreleme için)
    BIRIM_KEYWORDS = {
        "Fen": [
            "fen fakültesi", "fen fak", "biyoloji", "biyoteknoloji",
            "fizik bölümü", "kimya bölümü", "matematik bölümü",
        ],
        "IIBF": [
            "iibf", "iktisadi", "idari bilimler", "iktisat", "işletme",
            "maliye", "kamu yönetimi", "siyaset bilimi", "uluslararası ilişkiler",
        ],
        "Mimarlik": [
            "mimarlık", "mimari", "peyzaj mimarlığı", "şehir ve bölge planlama",
            "iç mimarlık", "mimar",
        ],
        "ITBF": [
            "itbf", "insan ve toplum bilimleri", "psikoloji", "sosyoloji",
            "tarih", "coğrafya", "türk dili", "edebiyat", "sanat tarihi",
            "mütercim", "tercümanlık", "batı dilleri",
        ],
    }

    @classmethod
    def ensure_directories(cls):
        """Gerekli dizinleri oluşturur."""
        cls.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
        cls.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
