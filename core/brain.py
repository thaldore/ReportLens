"""
ReportLens Çok Ajanlı Yönetim Merkezi.
Veri toplama, analiz, rapor yazma ve tutarsızlık kontrolü ajanlarını orkestre eder.
"""
import requests
from agno.agent import Agent
from agno.models.ollama import Ollama

from core.agents import (
    create_analyzer,
    create_consistency_checker,
    create_report_writer,
    create_mock_generator,
)
from core.config import Config
from core.logging_config import get_logger
from core.processor import ReportProcessor
from core.vector_store import VectorStore
from qdrant_client.models import Filter, FieldCondition, MatchValue

logger = get_logger(__name__)


class QualityBrain:
    """Kalite Analiz Sistemi – Çok Ajanlı Orkestrasyon."""

    def __init__(self):
        Config.ensure_directories()
        self._check_ollama_connection()

        self.model = Ollama(id=Config.MODEL_ID, host=Config.OLLAMA_BASE_URL)
        self.processor = ReportProcessor()
        self.vector_store = VectorStore()

        # Ajanları oluştur
        self.analyzer = create_analyzer(self.model)
        self.report_writer = create_report_writer(self.model)
        self.consistency_checker = create_consistency_checker(self.model)
        self.mock_generator = create_mock_generator(self.model)

        logger.info("QualityBrain başlatıldı. Tüm ajanlar hazır.")

    # ── Sağlık Kontrolleri ────────────────────────────────────────────

    def _check_ollama_connection(self):
        """Ollama servisinin erişilebilir olup olmadığını kontrol eder."""
        try:
            r = requests.get(f"{Config.OLLAMA_BASE_URL}/api/tags", timeout=5)
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            logger.info(f"Ollama bağlantısı başarılı. Yüklü modeller: {models}")

            if not any(Config.MODEL_ID in m for m in models):
                logger.warning(
                    f"⚠️ '{Config.MODEL_ID}' modeli bulunamadı! "
                    f"Lütfen 'ollama pull {Config.MODEL_ID}' çalıştırın."
                )
        except requests.ConnectionError:
            raise ConnectionError(
                f"Ollama servisine bağlanılamıyor ({Config.OLLAMA_BASE_URL}). "
                "Lütfen Ollama'nın çalıştığından emin olun."
            )
        except Exception as e:
            logger.warning(f"Ollama kontrol hatası: {e}")

    def get_status(self) -> dict:
        """Sistem durumu bilgisi döner."""
        import os

        raw_count = len(list(Config.RAW_DATA_DIR.glob("**/*"))) if Config.RAW_DATA_DIR.exists() else 0
        proc_count = len(list(Config.PROCESSED_DATA_DIR.glob("**/*.md"))) if Config.PROCESSED_DATA_DIR.exists() else 0
        db_info = self.vector_store.get_collection_info()

        return {
            "ham_rapor_sayisi": raw_count,
            "islenmiş_rapor_sayisi": proc_count,
            "vektor_db": db_info,
            "model": Config.MODEL_ID,
            "ollama_url": Config.OLLAMA_BASE_URL,
        }

    # ── Veri İşleme ──────────────────────────────────────────────────

    def process_and_index(self, force_reindex: bool = False) -> dict:
        """Raporları işler ve vektör veritabanını günceller."""
        processed = self.processor.convert_files()
        indexed = self.vector_store.index_documents(force_reindex=force_reindex)
        return {"islenen_dosya": processed, "indekslenen_chunk": indexed}

    # ── Genel Analiz ──────────────────────────────────────────────────

    def analyze(self, query: str, birim: str = None, yil: str = None) -> str:
        """Genel rapor analizi. Vektör araması + Analiz Ajanı."""
        context = self.vector_store.search(query, birim=birim, yil=yil)

        if not context.strip():
            return "Bu konuda vektör veritabanında ilgili bilgi bulunamadı. Lütfen raporların yüklenip indekslendiğinden emin olun."

        prompt = (
            f"Bağlam Verileri:\n{context}\n\n"
            f"Soru/Görev: {query}\n\n"
            "Yukarıdaki bağlam verilerine dayanarak soruyu detaylı bir şekilde yanıtla. "
            "Kaynaklardan aldığın bilgileri belirt."
        )

        response = self.analyzer.run(prompt)
        return response.content

    # ── Öz Değerlendirme Raporu ───────────────────────────────────────

    def generate_self_evaluation(self, birim: str, yil: str = None) -> str:
        """Birden fazla kalite raporundan öz değerlendirme raporu üretir."""
        criteria = [
            "Eğitim ve Öğretim süreçleri, müfredat, ders programları",
            "Araştırma ve Geliştirme faaliyetleri, yayınlar, projeler",
            "Toplumsal Katkı, sanayi işbirliği, etkinlikler",
            "Yönetim Sistemi, karar alma, organizasyon",
            "Öğrenci memnuniyeti, geri bildirim, anket sonuçları",
            "Kalite güvence süreçleri, PUKÖ döngüsü, iyileştirme",
        ]

        analyses = []
        for criterion in criteria:
            search_query = f"{birim} {criterion}"
            context = self.vector_store.search(search_query, birim=birim, yil=yil)

            if not context.strip():
                analyses.append(f"### {criterion}\n\nBu kriter için veri bulunamadı.")
                continue

            analysis_prompt = (
                f"Bağlam:\n{context}\n\n"
                f"{birim} birimi için '{criterion}' kriterini değerlendir.\n"
                "Güçlü yönleri, zayıf yönleri ve gelişim alanlarını belirle.\n"
                "Varsa sayısal verileri ve yıllar arası karşılaştırmayı ekle."
            )

            result = self.analyzer.run(analysis_prompt)
            analyses.append(f"### {criterion}\n\n{result.content}")
            logger.info(f"  📊 Kriter analizi tamamlandı: {criterion[:40]}...")

        # Tüm analizleri birleştirip rapor yaz
        combined = "\n\n---\n\n".join(analyses)
        report_prompt = (
            f"Aşağıdaki kriter analizlerini kullanarak {birim} birimi için "
            f"kapsamlı bir Öz Değerlendirme Raporu yaz:\n\n{combined}\n\n"
            "Raporu yapılandırılmış bölümlerle, akademik dilde yaz. "
            "Yönetici özeti ile başla, sonuç ve önerilerle bitir."
        )

        report = self.report_writer.run(report_prompt)
        return report.content

    # ── Belirli Rapor Analizi ──────────────────────────────────────────

    def analyze_single_report(self, filename: str) -> str:
        """Belirli bir raporun (dosya adı ile) içeriğini analiz eder."""
        # Soruya özel filtreleme (sadece o dosya)
        search_results = self.vector_store.client.scroll(
            collection_name=self.vector_store.collection_name,
            scroll_filter=Filter(
                must=[FieldCondition(key="dosya_adi", match=MatchValue(value=filename))]
            ),
            limit=100,
            with_payload=True
        )[0]

        if not search_results:
            return f"{filename} için veritabanında kayıt bulunamadı."

        full_content = "\n\n".join([p.payload.get("content", "") for p in search_results])
        
        prompt = (
            f"Dosya: {filename}\n"
            f"İçerik Özeti:\n{full_content[:15000]}\n\n"
            "Bu raporun kapsamlı bir analizini yap. "
            "Raporun amacı, ana çalışma alanları, belirtilen hedefler ve elde edilen sonuçları özetle. "
            "Kritik başarı faktörlerini ve varsa riskleri belirt."
        )

        response = self.analyzer.run(prompt)
        return response.content

    # ── Sahte Veri Üretimi ──────────────────────────────────────────────

    def generate_mock_data(self, filename: str, mode: str = "Tutarsız") -> str:
        """Seçilen rapor için tutarlı/tutarsız sahte veri üretir."""
        # Rapor içeriğinden daha geniş bir parça al (daha gerçekçi veri için)
        search_results = self.vector_store.client.scroll(
            collection_name=self.vector_store.collection_name,
            scroll_filter=Filter(
                must=[FieldCondition(key="dosya_adi", match=MatchValue(value=filename))]
            ),
            limit=20, # Daha fazla bağlam
            with_payload=True
        )[0]

        if not search_results:
            return "Veri üretmek için rapor içeriği bulunamadı."

        context = "\n".join([p.payload.get("content", "") for p in search_results])
        
        prompt = f"Rapor İçeriği:\n{context}\n\nMod: {mode}"
        response = self.mock_generator.run(prompt)
        return response.content

    # ── Tutarsızlık Analizi ───────────────────────────────────────────

    def check_consistency(self, comparison_text: str, birim: str = None, filename: str = None) -> str:
        """Rapor içeriği ile metin/anket karşılaştırması yapar."""
        if filename:
            # Sadece belirli bir raporla kıyasla - Tüm içeriği almaya çalış
            search_results = self.vector_store.client.scroll(
                collection_name=self.vector_store.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="dosya_adi", match=MatchValue(value=filename))]
                ),
                limit=150, # Raporun tamamına yakınını al
                with_payload=True
            )[0]
            context = "\n\n".join([p.payload.get("content", "") for p in search_results])
        else:
            # Genel arama - limit artırıldı (k=30)
            context = self.vector_store.search(comparison_text[:1000], birim=birim, k=30)

        if not context.strip():
            return "Karşılaştırma için ilgili rapor verisi bulunamadı."

        prompt = (
            f"Ground Truth (RAPOR İÇERİĞİ):\n{context}\n\n"
            f"Kıyaslanacak Veri (ANKET/METİN):\n{comparison_text}\n\n"
            "Görevin: Verinin rapordaki gerçeklerle ne kadar örtüştüğünü analiz et."
        )

        response = self.consistency_checker.run(prompt)
        return response.content
