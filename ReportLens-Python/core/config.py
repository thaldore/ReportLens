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

    # MSSQL Yapılandırması (Vector Search desteği ile)
    MSSQL_HOST = os.getenv("MSSQL_HOST", "reportlens-mssql-db")
    MSSQL_DB = os.getenv("MSSQL_DB", "ReportLensDB")
    MSSQL_USER = os.getenv("MSSQL_USER", "ReportLensUser")
    MSSQL_PASS = os.getenv("MSSQL_PASS", "ReportLensPass123!")
    MSSQL_DRIVER = os.getenv("MSSQL_DRIVER", "{ODBC Driver 18 for SQL Server}")
    MSSQL_TABLE = os.getenv("MSSQL_TABLE", "Python_DocumentVectors")


    # Vektör arama yapılandırması
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
    SEARCH_K = 20                 # Vektör aramadan dönecek en alakalı chunk sayısı
    
    # Maksimum bağlam limiti (8b model güvenli sınırı)
    MAX_CONTEXT_CHUNKS = 20       # Prompt'a girecek maksimum chunk (VRAM dostu)

    # Tutarsızlık analizi beyan boyutu limiti (karakter)
    MAX_COMPARISON_TEXT = int(os.getenv("MAX_COMPARISON_TEXT", "5000"))

    # Minimum chunk içerik uzunluğu (çok kısa chunk'ları filtrele)
    MIN_CHUNK_CONTENT_LENGTH = int(os.getenv("MIN_CHUNK_CONTENT_LENGTH", "50"))

    # Model parametreleri
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.1")) 
    MOCK_TEMPERATURE = float(os.getenv("MOCK_TEMPERATURE", "0.7"))
    NUM_CTX = 8192                # Bağlam penceresi (Daha geniş analiz kapasitesi için)

    # Prompt caching — modeli bellekte tut (Ollama keep_alive)
    OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "60m")

    # Re-ranker modeli (CPU üzerinde çalışır, GPU ile çakışma yok)
    RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() == "true"

    # Test sonuçları dizini
    TEST_RESULTS_DIR = BASE_DIR / "Data" / "test_results"

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

    # Birim kısaltma → tam ad eşleşmesi (halüsinasyon önleme)
    BIRIM_FULL_NAMES = {
        "Fen": "Fen Fakültesi",
        "IIBF": "İktisadi ve İdari Bilimler Fakültesi",
        "ITBF": "İnsan ve Toplum Bilimleri Fakültesi",
        "Mimarlik": "Mimarlık Fakültesi",
    }

    @classmethod
    def ensure_directories(cls):
        """Gerekli dizinleri oluşturur."""
        cls.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
        cls.IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        cls.TEST_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
