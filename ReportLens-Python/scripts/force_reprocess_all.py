"""
ReportLens Tam Yeniden İşleme Skripti.
Tüm işlenmiş verileri siler, Qdrant koleksiyonunu temizler ve her şeyi baştan işler.
Yeni pymupdf4llm ve OCR temizleme mantığını tüm dosyalara uygulamak için kullanılır.
"""
import shutil
from pathlib import Path
from core.config import Config
from core.brain import QualityBrain
from core.logging_config import get_logger

logger = get_logger(__name__)

def force_reprocess():
    logger.info("🚀 Tam yeniden işleme başlatılıyor...")

    # 1. İşlenmiş dosyaları temizle
    if Config.PROCESSED_DATA_DIR.exists():
        logger.info(f"  🗑️ Temizleniyor: {Config.PROCESSED_DATA_DIR}")
        shutil.rmtree(Config.PROCESSED_DATA_DIR)
        Config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Görselleri temizle
    if Config.IMAGES_DIR.exists():
        logger.info(f"  🗑️ Temizleniyor: {Config.IMAGES_DIR}")
        shutil.rmtree(Config.IMAGES_DIR)
        Config.IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # 3. QualityBrain başlat
    brain = QualityBrain()

    # 4. Qdrant koleksiyonunu sıfırla
    logger.info(f"  🧹 Vektör veritabanı sıfırlanıyor: {brain.vector_store.collection_name}")
    try:
        brain.vector_store.client.delete_collection(brain.vector_store.collection_name)
        # Sildikten sonra koleksiyonu tekrar oluşturmayı garanti et
        brain.vector_store._ensure_collection()
    except Exception as e:
        logger.warning(f"Koleksiyon sıfırlama hatası: {e}")

    # 5. Her şeyi yeniden işle ve indeksle
    logger.info("  ⚙️ Dosyalar dönüştürülüyor ve indeksleniyor (bu işlem zaman alabilir)...")
    result = brain.process_and_index(force_reindex=True)

    logger.info(f"✅ İşlem tamamlandı!")
    logger.info(f"   - İşlenen dosya: {result['islenen_dosya']}")
    logger.info(f"   - İndekslenen chunk: {result['indekslenen_chunk']}")

if __name__ == "__main__":
    force_reprocess()
