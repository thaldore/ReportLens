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

    def reprocess_empty_files(self) -> dict:
        """Boş/yetersiz işlenmiş dosyaları yeniden işler ve yeniden indeksler."""
        reprocessed = self.processor.reprocess_empty_files()
        if reprocessed > 0:
            indexed = self.vector_store.index_documents(force_reindex=False)
        else:
            indexed = 0
        return {"yeniden_islenen": reprocessed, "indekslenen_chunk": indexed}

    # ── Yardımcı: Sorgudan Birim ve Yıl Tespiti ────────────────────────

    def _detect_birim_from_query(self, query: str) -> str | None:
        """Sorgu metninden birim adını otomatik tespit eder (Config.BIRIM_KEYWORDS kullanır)."""
        q = query.lower()
        for birim, keywords in Config.BIRIM_KEYWORDS.items():
            if any(kw in q for kw in keywords):
                return birim
        return None

    def _detect_yil_from_query(self, query: str) -> str | None:
        """Sorgu metninden 4 haneli yıl tespit eder."""
        match = re.search(r"\b(20\d{2})\b", query)
        return match.group(1) if match else None

    # ── Genel Analiz ──────────────────────────────────────────────────

    def analyze(self, query: str, birim: str = None, yil: str = None) -> str:
        """Genel rapor analizi. Sorguda birim/yıl otomatik tespit edilip filtrelenerek arama yapılır."""
        # Kullanıcı belirtmediyse sorgudaki birim ve yılı otomatik tespit et
        if birim is None:
            birim = self._detect_birim_from_query(query)
        if yil is None:
            yil = self._detect_yil_from_query(query)

        if birim or yil:
            logger.info(f"Sorguda birim/yıl tespit edildi: birim={birim}, yil={yil}")

        context = self.vector_store.search(query, birim=birim, yil=yil)

        if not context.strip():
            return (
                "Bu konuda vektör veritabanında ilgili bilgi bulunamadı. "
                "Lütfen raporların yüklenip indekslendiğinden emin olun."
            )

        birim_info = f"Birim filtresi: **{birim}**" if birim else "Birim filtresi yok (tüm raporlar)"
        yil_info = f", Yıl filtresi: **{yil}**" if yil else ""

        prompt = (
            f"[{birim_info}{yil_info}]\n"
            f"Bağlam Verileri:\n{context}\n\n"
            f"Soru/Görev: {query}\n\n"
            "Yukarıdaki bağlam verilerine dayanarak soruyu yanıtla. "
            "Sadece sana sunulan birim ve yıla ait verileri kullan. "
            "Yanıtta somut sayı, tarih ve faaliyet adlarına yer ver."
        )

        response = self.analyzer.run(prompt)
        return response.content

    # ── Öz Değerlendirme Raporu ───────────────────────────────────────

    def generate_self_evaluation(self, birim: str, yil: str = None) -> str:
        """Birden fazla kalite raporundan öz değerlendirme raporu üretir."""
        criteria = [
            ("Liderlik ve Yonetim", "Misyon vizyon stratejik plan karar alma yonetim sistemi kalite guvence paydas katilimi"),
            ("Egitim ve Ogretim", "Program mufredat ogrenci sayisi AKTS ders ogrenci merkezli ogretim olcme degerlendirme sinav memnuniyet anketi"),
            ("Arastirma ve Gelistirme", "Arastirma AR-GE yayin proje TUBITAK BAP uluslararasi performans YOKSIS AKAPEDiA"),
            ("Toplumsal Katki", "Toplumsal katki staj sanayi isbirligi etkinlik seminer sosyal sorumluluk dis paydas"),
            ("Ogrenci Memnuniyeti", "Ogrenci memnuniyeti anket geri bildirim degerlendirme sonuc puan"),
            ("Kalite Guvence", "Kalite guvence PUKO dongusu iyilestirme ic denetim dis degerlendirme akreditasyon"),
        ]

        analyses = []
        for criterion_name, search_terms in criteria:
            search_query = f"{birim} {search_terms}"
            context = self.vector_store.search(search_query, birim=birim, yil=yil, k=12)

            if not context.strip() or not self._is_valid_context(context):
                analyses.append(f"### {criterion_name}\n\nBu kriter icin veritabaninda veri bulunamadi.")
                continue

            analysis_prompt = (
                f"Baglam Verileri:\n{context}\n\n"
                f"GOREV: '{birim}' birimi icin '{criterion_name}' kriterini degerlendir.\n"
                f"Sadece yukaridaki baglamdaki verileri kullan.\n"
                f"Yapilandirilmis cikti ver:\n"
                f"1. Mevcut Durum (somut veriler ve sayilarla — en az 2 paragraf)\n"
                f"2. Guclu Yonler (kanit ile)\n"
                f"3. Gelisim Alanlari (kanit ile)\n"
                f"4. Sayisal Veriler (varsa: ogrenci sayisi, proje sayisi, anket puani vb.)\n"
                f"Baglamda olmayan bilgi EKLEME. Veri yoksa 'Bu konuda yeterli veri bulunamamistir' de."
            )

            result = self.analyzer.run(analysis_prompt)
            analyses.append(f"### {criterion_name}\n\n{result.content}")
            logger.info(f"  Kriter analizi tamamlandi: {criterion_name}")

        # Tüm analizleri birleştirip rapor yaz
        combined = "\n\n---\n\n".join(analyses)
        
        yil_str = f" {yil}" if yil else ""
        report_prompt = (
            f"Asagidaki 6 kriter analizini kullanarak {birim} birimi icin{yil_str} "
            f"kapsamli bir Oz Degerlendirme Raporu yaz.\n\n"
            f"KRITER ANALIZLERI:\n{combined}\n\n"
            "ONEMLI KURALLAR:\n"
            "1. Her bolum EN AZ 2-3 paragraf olmali. Tek cumle veya liste ile gecistirme.\n"
            "2. Analizlerdeki somut verileri (sayi, tarih, isim) rapora aktar.\n"
            "3. Analizlerde olmayan bilgi UYDURMA.\n"
            "4. Raporu YOKAK yapisina uygun 7 bolumle yaz.\n"
            "5. 'Sunlari yapin' gibi tavsiye verme — mevcut durumu raporla.\n"
            "6. Toplam rapor en az 1500 kelime olmali."
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
            f"Belge Icerigi:\n{full_content[:15000]}\n\n"
            "GOREV: Bu raporu asagidaki yapisda kapsamli olarak analiz et.\n"
            "Her bolumde baglamdaki somut verileri kullan. Sayi uydurmak YASAKTIR.\n\n"
            "## 1. Rapor Turu ve Kapsami\n"
            "- Raporun turu (oz degerlendirme, eylem plani, tutanak vb.)\n"
            "- Hangi birimi kapsiyor, hangi yila ait\n\n"
            "## 2. Temel Sayisal Veriler\n"
            "- Ogrenci sayilari (program bazinda), program sayisi\n"
            "- Proje/yayin sayisi, anket sonuclari\n"
            "- Rakamsal verileri dogrudan rapordanAL, uydurmak YASAKTIR\n\n"
            "## 3. Ana Bulgular\n"
            "- Raporun one cikardigi en onemli 4-5 bulgu\n"
            "- Her bulgu icin somut kanit goster\n\n"
            "## 4. Guclu Yonler\n"
            "- Raporun olumlu vurguladigi alanlar (kanit ile)\n\n"
            "## 5. Zayif Yonler / Gelisim Alanlari\n"
            "- Raporda eksik veya sorunlu bulunan alanlar\n\n"
            "## 6. Eylem / Hedefler\n"
            "- Raporun onerdigi veya takip ettigi hedefler ve eylemler\n\n"
            "SADECE yukaridaki belgenin icerigine dayan. Tahmin veya genel bilgi ekleme."
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
            f"Rapor Icerigi:\n{context[:10000]}\n\n"
            "GOREV: Yukaridaki rapor icerigine dayanarak 2 AYRI bolum uret:\n"
            "1. BOLUM 1: ANKET YANITLARI — Markdown tablo formatinda (5-7 soru, 1-5 puan, isaretleme)\n"
            "2. BOLUM 2: METIN BEYANLARI — Paragraf halinde iddialar (4-6 cumle)\n"
            "Talimatlarindaki formati AYNEN izle. Bolum basliklarini degistirme."
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
                f"## 1. RAPOR ICERIGI (MUTLAK DOGRU — bu kaynaktaki her bilgi gercektir):\n"
                f"{context[:12000]}\n\n"
                f"## 2. KULLANICI BEYANLARI (bunlarin dogrulugunu test edeceksin):\n"
                f"{comparison_text}\n\n"
                "GOREV: Kullanici beyanlarindaki HER iddiavi ve anket yanitini AYRI AYRI analiz et.\n"
                "Her iddia icin SONUC etiketlemesi yap: DOGRU / YANLIS / BILGI YOK\n"
                "Rapor icerigi MUTLAK DOGRUDUR — rapordaki bilgiyi asla sorgulama.\n"
                "Talimatlarindaki formati (ANALIZ 1, ANALIZ 2, ANALIZ 3, OZET TABLOSU) izle."
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
                    f"Degerlendirilen Rapor: {filename}\n"
                    f"Kriter: {criterion_name} — {criterion_desc}\n\n"
                    f"BAGLAM (Yalnizca bu dosyadan alinan metin):\n{context}\n\n"
                    "GOREV: Yukaridaki baglama dayanarak bu kriteri 1-5 arasi puanla.\n"
                    "SADECE su 4 satiri yaz:\n"
                    "Puan: [1-5 tam sayi]/5\n"
                    "Gerekce: [neden bu puan]\n"
                    "Kanit: '[rapordaki alinti]'\n"
                    "Gelisim Onerisi: [somut adim]\n\n"
                    "UYARI: 4.5, 3.5, 8/10, ?/5 gibi formatlar YASAKTIR. Sadece 1, 2, 3, 4 veya 5."
                )
                eval_response = self.rubric_evaluator.run(eval_prompt)
                eval_content = eval_response.content

                # Evaluator çıktısından puan çıkar — birden fazla regex pattern dene
                puan_str = "?/5"
                puan_patterns = [
                    r"[Pp]uan\s*[:\-]?\s*(\d)\s*/\s*5",      # Puan: 4/5
                    r"[Pp]uan\s*[:\-]?\s*(\d)\b",              # Puan: 4
                    r"\b(\d)\s*/\s*5\b",                        # 4/5 anywhere
                ]
                for pattern in puan_patterns:
                    match = re.search(pattern, eval_content)
                    if match:
                        val = int(match.group(1))
                        if 1 <= val <= 5:
                            puan_str = f"{val}/5"
                            break

                # 2. Adım: Denetleme (Validator)
                val_prompt = (
                    f"Degerlendirilen Rapor: {filename}\n"
                    f"Kriter: {criterion_name}\n\n"
                    f"BAGLAM (Orijinal Rapor Metni):\n{context}\n\n"
                    f"YAPILAN PUANLAMA:\n{eval_content}\n\n"
                    "GOREV: Verilen puanin baglamla tutarli olup olmadigini denetle.\n"
                    "SADECE su 3 satiri yaz:\n"
                    "Karar: ONAYLANDI veya HATALI BULUNDU\n"
                    "Gozlem: [kanit dogrulama + tutarlilik — max 3 cumle]\n"
                    "Sonuc: Puan [X]/5 olmalidir — [kisa gerekce]"
                )
                val_response = self.rubric_validator.run(val_prompt)
                val_content = val_response.content

                # Denetim kararını özet için çıkar (çeşitli onay ifadelerini yakala)
                _vc_lower = val_content.lower()
                _approved = any(kw in _vc_lower for kw in [
                    "onaylandi", "onaylandı", "dogrudur", "doğrudur", "✅ onaylandi",
                    "tutarli", "tutarlı", "dogru bulundu", "doğru bulundu",
                ])
                karar = "✅ Onay" if _approved else "❌ Düzeltme"
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
