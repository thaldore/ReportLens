"""
ReportLens Vektör Veritabanı Kontrol Scripti.
Qdrant koleksiyonundaki veri sayısını ve durumunu gösterir.
"""
from core.config import Config
from core.vector_store import VectorStore


def check_db():
    try:
        store = VectorStore()
        info = store.get_collection_info()
        print(f"Koleksiyon: {Config.QDRANT_COLLECTION}")
        print(f"Toplam vektör noktası: {info.get('toplam_nokta', 0)}")
        print(f"Vektör boyutu: {info.get('vektör_boyutu', '-')}")
        print(f"Durum: {info.get('durum', '-')}")
    except Exception as e:
        print(f"Hata: {e}")


if __name__ == "__main__":
    check_db()
