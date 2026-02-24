"""
ReportLens Çok Ajanlı Yönetim Merkezi.
Veri toplama, analiz, rapor yazma ve tutarsızlık kontrolü ajanlarını orkestre eder.
"""
import re
import requests
from agno.agent import Agent
from agno.models.ollama import Ollama

from core.agents import (
    create_analyzer,
    create_consistency_checker,
    create_report_writer,
    create_mock_generator,
    create_rubric_evaluator,
    create_rubric_validator,
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
        self.rubric_evaluator = create_rubric_evaluator(self.model)
        self.rubric_validator = create_rubric_validator(self.model)

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
            f"Asagidaki kriter analizlerini kullanarak {birim} birimi icin "
            f"kapsamli bir Oz Degerlendirme Raporu yaz:\n\n{combined}\n\n"
            "Raporun yapisi YOKAK standartlarina uygun olarak su 7 ana bolumden olusmalidir:\n"
            "1. Yonetici Ozeti (en az 3 paragraf — somut sayilarla)\n"
            "2. A. Liderlik ve Yonetim (A.1 Kalite Sistemi, A.2 Stratejik Plan, A.3 Kararlar, A.4 Paydas)\n"
            "3. B. Egitim ve Ogretim (program, ders icerigi, akreditasyon, ogretim elemani ort. yuku)\n"
            "4. C. AR-GE Faaliyetleri (proje sayisi, yayin, TUS/YOKSIS verileri)\n"
            "5. D. Toplumsal Katki (etkinlik, kariyer, sanayi islbirligi)\n"
            "6. Guclu Yonler vs Gelistirilmesi Gereken Alanlar (karsilastirmali tablo)\n"
            "7. Sonuc ve Eylem Plani (PUKO tablosu: | Eylem | Sorumlu | Sure | Beklenen Sonuc |)\n"
            "Her bolum en az 2-3 paragraf olmali. Baglamda somut veri yoksa varsayimsal bilgi ekleme."
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
        """Seçilen rapor için hem Anket hem Metin içeren hibrit sahte veri üretir."""
        # Rapor içeriğinden daha geniş bir parça al (daha gerçekçi veri için)
        try:
            search_results = self.vector_store.client.scroll(
                collection_name=self.vector_store.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="dosya_adi", match=MatchValue(value=filename))]
                ),
                limit=20,
                with_payload=True
            )[0]
            context = "\n".join([p.payload.get("content", "") for p in search_results])
        except Exception:
            context = self.vector_store.search("", filename=filename, k=15)

        if not context:
            return "Veri üretmek için rapor içeriği bulunamadı."
        
        prompt = (
            f"Dosya: {filename}\n"
            f"Mod: {mode}\n"
            f"Rapor İçeriği:\n{context[:10000]}\n\n"
            "Talimatlarina uygun olarak BOLUM 1 (Anket Yanitlari tablosu) ve BOLUM 2 (Analiz Metni) bolumleri uret."
        )
        response = self.mock_generator.run(prompt)
        return response.content

    # ── Tutarsızlık Analizi ───────────────────────────────────────────

    def check_consistency(self, comparison_text: str, birim: str = None, filename: str = None) -> str:
        """Rapor içeriği ile metin/anket karşılaştırması yapar."""
        try:
            if filename:
                # Sadece belirli bir raporla kıyasla - Kapsamı model sınırları içinde tut
                try:
                    search_results = self.vector_store.client.scroll(
                        collection_name=self.vector_store.collection_name,
                        scroll_filter=Filter(
                            must=[FieldCondition(key="dosya_adi", match=MatchValue(value=filename))]
                        ),
                        limit=Config.MAX_CONTEXT_CHUNKS,
                        with_payload=True
                    )[0]
                    context = "\n\n".join([p.payload.get("content", "") for p in search_results])
                except Exception as e:
                    logger.warning(f"Scroll hatası, search'e dönülüyor: {str(e)}")
                    context = self.vector_store.search("", k=Config.MAX_CONTEXT_CHUNKS, filename=filename)
            else:
                # Genel arama
                context = self.vector_store.search(comparison_text[:500], birim=birim, k=Config.MAX_CONTEXT_CHUNKS)

            if not context or "hata" in str(context).lower():
                return "Karşılaştırma için yeterli rapor verisi bulunamadı."

            prompt = (
                f"Sana analiz etmen icin iki bolum veriyorum:\n\n"
                f"1. RAPOR ICERIGI (Mutlak Gercek):\n{context}\n\n"
                f"2. KIYASLANACAK HIBRIT VERI (Anket Tablosu + Analiz Metni):\n{comparison_text}\n\n"
                "Talimatlarindaki gibi ANALIZ 1 (Rapor Icerigi Ozeti) ve ANALIZ 2 (Tutarlilik Analizi) "
                "seklinde IKI AYRI bolum uret. "
                "ANALIZ 2 icerisinde 2a (Anket Puanlari) ve 2b (Metin Ifadeleri) alt bolumleri ve "
                "zorunlu karsilastirma tablosu olmalidir."
            )
            response = self.consistency_checker.run(prompt)
            return response.content
        except Exception as e:
            logger.error(f"Tutarsızlık analizi hatası: {str(e)}")
            return f"Analiz sırasında bir hata oluştu: {str(e)}"

    # ── Yardımcı: Hata string tespiti ───────────────────────────────────

    @staticmethod
    def _is_valid_context(context: str) -> bool:
        """Vektör arama sonucunun gerçek içerik mi yoksa hata mesajı mı olduğunu kontrol eder."""
        if not context or not context.strip():
            return False
        error_markers = [
            "sorun oluştu", "hata", "bulunamadı", "error", "no such attribute",
            "QdrantClient", "arama hatası", "kritik arama"
        ]
        lower = context.lower()
        # Kısa hata string'i mi? (gerçek içerik genellikle çok daha uzun)
        if len(context) < 200 and any(m in lower for m in error_markers):
            return False
        return True

    # ── Rubrik Notlandırma ───────────────────────────────────────────

    def evaluate_rubric(self, filenames: list) -> str:
        """Bir veya birden fazla raporu rubrik kriterlerine göre değerlendirir."""
        if not filenames:
            return "Değerlendirilecek rapor seçilmedi."

        overall_results = []
        overall_results.append(f"# 📊 Rubrik Notlandırma Raporu\n")
        overall_results.append(f"**Değerlendirilen Raporlar:** {', '.join(filenames)}\n")

        for filename in filenames:
            overall_results.append(f"## 📄 Rapor: {filename}")
            
            report_analyses = []
            # Özet tablo için puan takibi
            summary_rows = []

            for criterion_name, criterion_desc in Config.RUBRIC_CRITERIA.items():
                logger.info(f"  📏 Rubrik Değerlendirmesi: {filename} -> {criterion_name}")
                
                # ✅ FIX: Sadece değerlendirilen dosyaya ait chunk'ları getir (birim kirlenmesi önlendi)
                search_query = f"{criterion_name} {criterion_desc}"
                context = self.vector_store.search(
                    search_query,
                    k=15,
                    filename=filename,  # Yalnızca bu dosyanın chunk'larını al
                )

                # ✅ FIX: Hata string'i LLM bağlamına sızmasın
                if not self._is_valid_context(context):
                    no_data_msg = (
                        f"### 📏 {criterion_name}\n\n"
                        f"⚠️ Bu dosya için kriter bağlamı bulunamadı. "
                        f"Raporun bu bölümü eksik veya indekslenmemiş olabilir.\n\n"
                        f"**--- 🤖 RUBRİK DENETİMİ ---**\n"
                        f"Değerlendirme yapılamadı (bağlam yok).\n"
                        f"{'-' * 40}"
                    )
                    report_analyses.append(no_data_msg)
                    summary_rows.append(f"| {criterion_name} | —/5 | ⚠️ Bağlam Yok |")
                    continue

                # 1. Adım: Değerlendirme (Evaluator)
                eval_prompt = (
                    f"Değerlendirilen Rapor: **{filename}**\n"
                    f"Kriter: **{criterion_name}** — {criterion_desc}\n\n"
                    f"BAĞLAM (Yalnızca bu dosyadan alınan metin):\n{context}\n\n"
                    "Lütfen talimatlarındaki 1-5 formatına göre yalnızca yukarıdaki bağlama dayanarak puanlamanı yap. "
                    "Başka raporlardan veya genel bilgiden faydalanma."
                )
                eval_response = self.rubric_evaluator.run(eval_prompt)
                eval_content = eval_response.content

                # ✅ FIX: Evaluator çıktısından tahmini puan çıkar (özet tablo için)
                puan_match = re.search(r"\*?\*?Puan\*?\*?\s*[:\-]?\s*(\d)[/\d]*", eval_content)
                puan_str = f"{puan_match.group(1)}/5" if puan_match else "?/5"

                # 2. Adım: Denetleme (Validator)
                val_prompt = (
                    f"Değerlendirilen Rapor: **{filename}**\n"
                    f"Kriter: **{criterion_name}**\n\n"
                    f"BAĞLAM (Orijinal Rapor Metni):\n{context}\n\n"
                    f"YAPILAN PUANLAMA:\n{eval_content}\n\n"
                    "Lütfen denetimini yap: Verilen puan bağlamla tutarlı mı? Karar, Analiz ve Sonuç formatında yaz."
                )
                val_response = self.rubric_validator.run(val_prompt)
                val_content = val_response.content

                # Denetim kararını özet için çıkar
                karar = "✅ Onay" if "doğrudur" in val_content.lower() or "onaylandı" in val_content.lower() else "❌ Düzeltme"
                summary_rows.append(f"| {criterion_name} | {puan_str} | {karar} |")
                
                # Kriter bazlı birleştirme
                criterion_result = (
                    f"### 📏 {criterion_name}\n"
                    f"{eval_content}\n\n"
                    f"#### 🛡️ DENETİM\n"
                    f"{val_content}\n"
                    f"{'-' * 40}"
                )
                report_analyses.append(criterion_result)

            # Özet tablo
            summary_table = (
                f"\n\n### 📋 {filename} — Özet Puan Tablosu\n\n"
                f"| Kriter | Değerlendirici Puanı | Denetim Kararı |\n"
                f"| :--- | :---: | :---: |\n"
                + "\n".join(summary_rows)
            )

            overall_results.append("\n\n---\n\n".join(report_analyses))
            overall_results.append(summary_table)
            overall_results.append("\n---")

        return "\n\n".join(overall_results)
