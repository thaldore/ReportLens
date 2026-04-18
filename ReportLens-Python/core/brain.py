"""
ReportLens Çok Ajanlı Yönetim Merkezi.
Veri toplama, analiz, rapor yazma ve tutarsızlık kontrolü ajanlarını orkestre eder.
Prompt caching (keep_alive), re-ranking ve birim kısaltma doğrulama destekler.
"""
import os
# Agno telemetrisini kapat — veri gizliliği (os-api.agno.com'a veri gönderimini engelle)
os.environ["AGNO_TELEMETRY"] = "false"

from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from core.output_validator import OutputValidator
from core.processor import ReportProcessor
from core.vector_store import VectorStore
# from qdrant_client.models import Filter, FieldCondition, MatchValue (Kaldırıldı)


logger = get_logger(__name__)


class QualityBrain:
    """Kalite Analiz Sistemi – Çok Ajanlı Orkestrasyon."""

    def __init__(self):
        Config.ensure_directories()
        self._check_ollama_connection()

        # Ana model — prompt caching ile (keep_alive)
        self.model = Ollama(
            id=Config.MODEL_ID,
            host=Config.OLLAMA_BASE_URL,
            options={
                "temperature": Config.TEMPERATURE,
                "num_ctx": Config.NUM_CTX,
                "repeat_penalty": 1.2, # Tekrarları önlemek için
            },
            keep_alive=Config.OLLAMA_KEEP_ALIVE,
        )

        # Mock veri için ayrı model (daha yüksek sıcaklık)
        self.mock_model = Ollama(
            id=Config.MODEL_ID,
            host=Config.OLLAMA_BASE_URL,
            options={
                "temperature": Config.MOCK_TEMPERATURE,
                "num_ctx": Config.NUM_CTX,
            },
            keep_alive=Config.OLLAMA_KEEP_ALIVE,
        )

        self.processor = ReportProcessor()
        self.vector_store = VectorStore()

        # Ajanları oluştur
        self.analyzer = create_analyzer(self.model)
        self.report_writer = create_report_writer(self.model)
        self.consistency_checker = create_consistency_checker(self.model)
        self.mock_generator = create_mock_generator(self.mock_model)
        self.rubric_evaluator = create_rubric_evaluator(self.model)
        self.rubric_validator = create_rubric_validator(self.model)

        logger.info("QualityBrain başlatıldı. Tüm ajanlar hazır. "
                     f"Prompt caching: keep_alive={Config.OLLAMA_KEEP_ALIVE}")

    # ── Sağlık Kontrolleri ────────────────────────────────────────────

    def _check_ollama_connection(self):
        """Ollama servisinin ve gerekli modellerin (LLM + Embedding) kontrolünü yapar."""
        try:
            r = requests.get(f"{Config.OLLAMA_BASE_URL}/api/tags", timeout=5)
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            logger.info(f"Ollama bağlantısı başarılı. Yüklü modeller: {models}")

            # Ana model kontrolü
            if not any(Config.MODEL_ID in m for m in models):
                logger.warning(
                    f"⚠️ Ana model '{Config.MODEL_ID}' bulunamadı! "
                    f"Lütfen 'ollama pull {Config.MODEL_ID}' çalıştırın."
                )
            
            # Embedding model kontrolü
            if not any(Config.EMBEDDING_MODEL in m for m in models):
                logger.error(
                    f"❌ Embedding modeli '{Config.EMBEDDING_MODEL}' bulunamadı! "
                    f"Vektör indeksleme çalışmayacaktır. Lütfen 'ollama pull {Config.EMBEDDING_MODEL}' çalıştırın."
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
        raw_count = len(list(Config.RAW_DATA_DIR.glob("**/*"))) if Config.RAW_DATA_DIR.exists() else 0
        proc_count = len(list(Config.PROCESSED_DATA_DIR.glob("**/*.md"))) if Config.PROCESSED_DATA_DIR.exists() else 0
        db_info = self.vector_store.get_collection_info()

        return {
            "ham_rapor_sayisi": raw_count,
            "islenmiş_rapor_sayisi": proc_count,
            "vektor_sayisi": db_info.get("toplam_nokta", 0),
            "toplam_nokta": db_info.get("toplam_nokta", 0),
            "durum": db_info.get("durum", "bilinmiyor"),
            "model": Config.MODEL_ID,
            "embedding_model": Config.EMBEDDING_MODEL,
            "ollama_url": Config.OLLAMA_BASE_URL,
            "keep_alive": Config.OLLAMA_KEEP_ALIVE,
            "num_ctx": Config.NUM_CTX,
            "mssql_host": Config.MSSQL_HOST,
            "mssql_db": Config.MSSQL_DB,
            "reranker_enabled": Config.RERANKER_ENABLED,
            "reranker": "aktif" if Config.RERANKER_ENABLED else "devre dışı",
            "prompt_cache": Config.OLLAMA_KEEP_ALIVE,
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
        """Sorgu metninden birim adını otomatik tespit eder."""
        q = query.lower()
        for birim, keywords in Config.BIRIM_KEYWORDS.items():
            if any(kw in q for kw in keywords):
                return birim
        return None

    def _detect_yil_from_query(self, query: str) -> str | None:
        """Sorgu metninden 4 haneli yıl tespit eder."""
        match = re.search(r"\b(20\d{2})\b", query)
        return match.group(1) if match else None

    @staticmethod
    def _get_birim_full_name(birim: str) -> str:
        """Birim kısaltmasını tam ada çevirir."""
        return Config.BIRIM_FULL_NAMES.get(birim, birim or "")

    # ── Genel Analiz ──────────────────────────────────────────────────

    def analyze(self, query: str, birim: str = None, yil: str = None) -> tuple:
        """Genel rapor analizi. Returns: (result_text, detected_birim, detected_yil)"""
        auto_birim = None
        auto_yil = None
        if birim is None:
            auto_birim = self._detect_birim_from_query(query)
            birim = auto_birim
        if yil is None:
            auto_yil = self._detect_yil_from_query(query)
            yil = auto_yil

        if birim or yil:
            logger.info(f"Sorguda birim/yıl tespit edildi: birim={birim}, yil={yil}")

        context_raw = self.vector_store.search(query, birim=birim, yil=yil, k=40)
        
        # Re-ranking (Yeniden Sıralama)
        from core.reranker import rerank
        context_list = context_raw.split("\n\n---\n\n")
        reranked = rerank(query, context_list, top_k=Config.SEARCH_K)
        context = "\n\n---\n\n".join([r[1] for r in reranked])

        if not context.strip():
            return (
                "Bu konuda vektör veritabanında ilgili bilgi bulunamadı. "
                "Lütfen raporların yüklenip indekslendiğinden emin olun.",
                auto_birim, auto_yil,
            )

        birim_full = self._get_birim_full_name(birim)
        birim_info = f"Birim filtresi: **{birim_full}** ({birim})" if birim else "Birim filtresi yok (tüm raporlar)"
        yil_info = f", Yıl filtresi: **{yil}**" if yil else ""

        prompt = (
            f"### ANALYSIS FILTER: [{birim_info}{yil_info}]\n\n"
            f"### CONTEXT DATA (REPORT EXCERPTS):\n{context}\n\n"
            f"### TASK: Provide a detailed and academic analysis of the question: '{query}' based ONLY on the data above.\n\n"
            "### CORE RULES:\n"
            "1. EVIDENCE: Every claim or finding MUST include a source. Format: (Kaynak: filename.md)\n"
            "2. STRUCTURE: Use the exact headers defined in the template below.\n"
            "3. DATA-DRIVEN: Prioritize numerical data, statistics, and specific system names.\n\n"
            "### OUTPUT TEMPLATE (YOUR ENTIRE RESPONSE MUST BE IN TURKISH):\n"
            "## 1. ANALIZ KAPSAMI\n"
            "(Which unit, year, and specific topic is being analyzed?)\n\n"
            "## 2. TEMEL BULGULAR VE KANITLAR\n"
            "- [Finding Description] (Kaynak: Dosya_Adi.md)\n"
            "- [Data/Statistic] (Kaynak: Dosya_Adi.md)\n\n"
            "## 3. GÜÇLÜ YÖNLER VE BAŞARILAR\n"
            "- [Strong Point] (Kaynak: Dosya_Adi.md)\n\n"
            "## 4. GELİŞİME AÇIK ALANLAR VE RİSKLER\n"
            "- [Area for Improvement] (Kaynak: Dosya_Adi.md)\n\n"
            "## 5. STRATEJİK ÖNERİLER VE SONUÇ\n"
            "- [Concrete, applicable recommendation]\n\n"
            "### CRITICAL NOTE: Your response must be academic, objective, and strictly evidence-based."
        )

        response = self.analyzer.run(prompt)
        result = OutputValidator.validate_full_output(
            response.content, context,
            expected_sections=["ANALIZ KAPSAMI", "TEMEL BULGULAR", "GUCLU YONLER", "GELISIME ACIK ALANLAR", "ONERILER"],
            expected_birim=birim,
        )
        return result, auto_birim, auto_yil

    # ── Öz Değerlendirme Raporu ───────────────────────────────────────

    def generate_self_evaluation(self, birim: str, yil: str = None) -> str:
        """Birden fazla kalite raporundan öz değerlendirme raporu üretir.
        Multi-step LLM: Her kriter ayrı çağrı + birleştirme.
        """
        birim_full = self._get_birim_full_name(birim)
        
        # 1. Her kriteri analiz et (Sıralı - VRAM Güvenliği için)
        criteria_analyses = []
        criterion_data = list(Config.RUBRIC_CRITERIA.items())
        
        for cid, desc in criterion_data:
            logger.info(f"  ⏳ Kriter analiz ediliyor: {cid}")
            context = self.vector_store.search(
                f"{cid} {desc}", 
                birim=birim, 
                yil=yil, 
                k=Config.MAX_CONTEXT_CHUNKS
            )
            
            prompt = (
                f"Unit: {birim_full} ({birim})\nYear: {yil if yil else 'All'}\n"
                f"Quality Criterion: {cid}\n"
                f"Context Data:\n{context}\n\n"
                f"TASK: Analyze the 'Strengths' and 'Areas for Improvement' for this specific criterion based ONLY on the evidence. "
                "You MUST include at least one concrete data point or direct report excerpt. "
                "YOUR RESPONSE MUST BE IN ACADEMIC TURKISH."
            )
            response = self.analyzer.run(prompt)
            criteria_analyses.append(f"### {cid}\n{response.content[:2500]}")

        # 2. Sentez Raporu Oluştur
        logger.info(f"  📝 {birim} için rapor sentezleniyor...")
        full_context = "\n\n".join(criteria_analyses)
        
        sections = ["YONETICI OZETI", "LIDERLIK", "EGITIM", "ARASTIRMA", "TOPLUMSAL KATKI", "GUCLU YONLER", "SONUC"]
        report_prompt = (
            f"Unit: {birim_full} ({birim})\nYear: {yil if yil else 'All'}\n\n"
            f"CRITERIA ANALYSES:\n{full_context}\n\n"
            "TASK: Create a formal Self-Assessment Report in YOKAK format using the analyses provided above.\n"
            "MANDATORY RULES:\n"
            "1. STRUCTURE: ALL following headers must be present in the output: ## Yonetici Ozeti, ## Liderlik, ## Egitim, ## Arastirma, ## Toplumsal Katki, ## Guclu Yonler, ## Sonuc\n"
            "2. DATA GAP: If there is insufficient data for a section, write 'Bu alanda spesifik veri bulunamamıştır' but KEEP the header.\n"
            "3. FORMAT: Write headers as Markdown H2 (##).\n"
            "4. LANGUAGE: YOUR ENTIRE REPORT MUST BE IN FORMAL ACADEMIC TURKISH."
        )
        response = self.report_writer.run(report_prompt)
        
        result = OutputValidator.validate_full_output(
            response.content, 
            full_context,
            expected_sections=sections,
            expected_birim=birim,
        )
        return result

    # ── Belirli Rapor Analizi ──────────────────────────────────────────

    def analyze_single_report(self, filename: str) -> str:
        """Belirli bir raporun (dosya adı ile) içeriğini analiz eder."""
        # 1. Geniş Kapsamlı Arama
        anchors = [
             "Raporun genel özeti ve temel sayısal veriler",
             "Eğitim öğretim, güçlü yanlar ve gelişim alanları",
             "Araştırma geliştirme, toplumsal katkı ve gelecek hedefleri"
        ]
        
        context_parts = []
        for anchor in anchors:
            res = self.vector_store.search(anchor, k=10, filename=filename) # K artırıldı
            context_parts.append(res)
        
        full_context = "\n\n---\n\n".join(context_parts)

        metadata = VectorStore.parse_metadata(filename)
        birim = metadata.get("birim", "")
        birim_full = self._get_birim_full_name(birim)
        meta_info = (
            f"Rapor Metadata:\n"
            f"- Birim: {birim_full} ({birim})\n"
            f"- Yil: {metadata.get('yil', 'Bilinmiyor')}\n"
            f"- Tur: {metadata.get('tur', 'Bilinmiyor')}\n"
        )

        prompt = (
            f"### DETAILED REPORT ANALYSIS: {filename}\n"
            f"{meta_info}\n"
            f"### CONTEXT DATA (REPORT EXCERPTS):\n{full_context}\n\n"
            "### TASK: Analyze this report in depth according to the template below.\n\n"
            "### CORE RULES:\n"
            "1. EVIDENCE: For each section, provide CONCRETE EVIDENCE and DATA (numbers, ratios) from the report.\n"
            "2. STRUCTURE: Use H2 (##) headers exactly as named in the template.\n"
            "3. CITATION: Use ONLY the format (Kaynak: {filename}) for citations.\n"
            "4. LANGUAGE: YOUR ENTIRE RESPONSE MUST BE IN FORMAL TURKISH.\n\n"
            "## 1. RAPOR TURU VE KAPSAMI\n"
            " (Purpose of the report, period covered, and unit information)\n\n"
            "## 2. TEMEL SAYISAL VERİLER VE İSTATİSTİKLER\n"
            "- Student/Faculty Data: ...\n"
            "- Success/Satisfaction Ratios: ...\n\n"
            "## 3. ANA BULGULAR VE DEĞERLENDİRME\n"
            "- [Finding]: [Explanation]\n\n"
            "## 4. GÜÇLÜ YÖNLER\n"
            "- [Success Area]: [Detailed Explanation] (Kaynak: {filename})\n\n"
            "## 5. ZAYIF YÖNLER VE RİSKLER\n"
            "- [Weakness]: [Area needing improvement] (Kaynak: {filename})\n\n"
            "## 6. EYLEM PLANLARI VE HEDEFLER\n"
            "- [Goal]: [Reported future plan]\n\n"
            "### CRITICAL WARNING: If data is missing for a section, write 'İlgili veri raporda açıkça belirtilmemiştir'."
        )

        response = self.analyzer.run(prompt)
        result = OutputValidator.validate_full_output(
            response.content, full_context,
            expected_sections=["RAPOR TURU", "SAYISAL VERILER", "ANA BULGULAR", "GUCLU YONLER", "ZAYIF YONLER", "EYLEM / HEDEFLER"],
            expected_birim=birim,
        )
        return result

    # ── Sahte Veri Üretimi ──────────────────────────────────────────────

    def generate_mock_data(self, filename: str, mode: str = "Tutarsız") -> str:
        """Seçilen rapor için hem Anket hem Metin içeren hibrit sahte veri üretir."""
        try:
            search_results = self.vector_store.get_file_content(filename, limit=20)
            context = "\n".join([p.get("content", "") for p in search_results])
        except Exception:
            context = self.vector_store.search("", filename=filename, k=15)

        if not context:
            return "Veri üretmek için rapor içeriği bulunamadı."
        
        prompt = (
            f"File: {filename}\n"
            f"Generation Mode: {mode}\n"
            f"Report Content:\n{context[:10000]}\n\n"
            "TASK: Generate 2 SEPARATE blocks. Use the EXACT markers below.\n\n"
            "[ANKET_VERISI]\n"
            "(Generate a Markdown table with columns: #, Soru, Puan (1-5), Isaretleme)\n\n"
            "[METIN_BEYANLARI]\n"
            "(Generate 4-6 sentences of claims/paragraphs with [GT:DOGRU] or [GT:YANLIS] tags)\n\n"
            "CRITICAL: Start the first block with [ANKET_VERISI] and the second with [METIN_BEYANLARI]."
        )

        response = self.mock_generator.run(prompt)
        result = response.content

        if "[ANKET_VERISI]" not in result or "[METIN_BEYANLARI]" not in result:
            retry_prompt = prompt + "\n\nIMPORTANT: You MUST use the [ANKET_VERISI] and [METIN_BEYANLARI] tags."
            response = self.mock_generator.run(retry_prompt)
            result = response.content

        return result

    # ── Tutarsızlık Analizi ───────────────────────────────────────────

    def check_consistency(
        self,
        comparison_text: str,
        survey_text: str = None,
        birim: str = None,
        filename: str = None,
    ) -> str:
        """Rapor içeriği ile metin/anket karşılaştırması yapar."""
        try:
            comparison_text = comparison_text[:Config.MAX_COMPARISON_TEXT]
            if survey_text:
                survey_text = survey_text[:Config.MAX_COMPARISON_TEXT]

            if filename:
                # İsimlendirilmiş parçaları ara
                search_query = f"{comparison_text[:1000]} {survey_text[:500] if survey_text else ''}"
                context = self.vector_store.search(search_query, k=25, filename=filename) # K artırıldı
            else:
                if birim is None:
                    birim = self._detect_birim_from_query(comparison_text)
                context = self.vector_store.search(comparison_text[:1000], birim=birim, k=25)

            if not context or not self._is_valid_context(context):
                return "Karşılaştırma için yeterli rapor verisi bulunamadı."

            user_claims = ""
            if survey_text:
                user_claims += f"### ANKET VERILERI:\n{survey_text}\n\n"
            user_claims += f"### KULLANICI BEYANLARI:\n{comparison_text}"

            prompt = (
                f"### CONSISTENCY ANALYSIS: {filename if filename else birim}\n"
                f"### 1. REPORT CONTENT (CONTEXT):\n{context}\n\n"
                f"### 2. CLAIMS TO VERIFY:\n{user_claims}\n\n"
                "### TASK: Compare the claims above with the report content. For each claim, decide: [DOĞRU / YANLIŞ / BİLGİ YOK].\n"
                "### CORE RULES:\n"
                "1. Decisions must be based ONLY on what is written in the report.\n"
                "2. If a claim is WRONG, you MUST provide the correct fact with evidence.\n"
                "3. YOUR ENTIRE RESPONSE MUST BE IN TURKISH.\n\n"
                "### ZORUNLU FORMAT:\n"
                "### ANALIZ 1\n"
                "- Beyan: ...\n"
                "- Karar: ...\n"
                "- Kanıt: (Kaynak: {filename})\n\n"
                "### OZET TABLOSU\n"
                "| # | Beyan | Karar | Kanıt/Not |\n"
                "|---|---|---|---|\n"
            )
            response = self.consistency_checker.run(prompt)
            result = OutputValidator.validate_full_output(
                response.content, context,
                expected_sections=["ANALIZ 1", "OZET TABLOSU"]
            )
            return result
        except Exception as e:
            logger.error(f"Tutarsızlık analizi hatası: {str(e)}")
            return f"Analiz sırasında bir hata oluştu: {str(e)}"

    # ── Yardımcı: Hata string tespiti ───────────────────────────────────

    @staticmethod
    def _is_valid_context(context: str) -> bool:
        """Vektör arama sonucunun gerçek içerik mi yoksa hata mesajı mı olduğunu kontrol eder."""
        if not context or not context.strip():
            return False
        error_markers = ["sorun oluştu", "hata", "bulunamadı", "error", "MSSQL"]
        lower = context.lower()
        if len(context) < 200 and any(m in lower for m in error_markers):
            return False
        return True

    # ── Rubrik Notlandırma ───────────────────────────────────────────

    def evaluate_rubric(self, filenames: list) -> str:
        """Bir veya birden fazla raporu rubrik kriterlerine göre 'Altın Standart' kıyaslama formatında değerlendirir."""
        if not filenames:
            return "Değerlendirilecek rapor seçilmedi."

        import datetime
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        overall_results = []
        overall_results.append(f"# 📊 ReportLens Rubrik Ve Denetim Raporu\n")
        overall_results.append(f"**Tarih:** {now_str}")
        overall_results.append(f"**Değerlendirilen Raporlar:** {', '.join(filenames)}\n")
        overall_results.append(f"## 📋 Analiz Özeti\n| Rapor | Kriter Sayısı | Denetim Durumu |\n| :--- | :---: | :---: |\n" + "\n".join([f"| {f} | {len(Config.RUBRIC_CRITERIA)} | 🛡️ Bekliyor |" for f in filenames]))
        overall_results.append("\n---\n")

        for filename in filenames:
            logger.info(f"  📏 Rubrik Analiz/Denetim Başlıyor: {filename}")
            
            # 1. BAĞLAM TOPLAMA
            all_criteria_context = []
            for criterion_name, criterion_desc in Config.RUBRIC_CRITERIA.items():
                res = self.vector_store.search(f"{criterion_name} {criterion_desc}", k=8, filename=filename)
                all_criteria_context.append(f"### KRİTER: {criterion_name}\n{res}")
            
            full_context = "\n\n---\n\n".join(all_criteria_context)

            # 2. ADIM: DETAYLI ANALİZ (Batch 1)
            analiz_prompt = (
                f"### REPORT: {filename}\n"
                f"### CONTEXT DATA:\n{full_context}\n\n"
                "TASK: Perform a detailed analysis of the report according to YOKAK rubric criteria.\n"
                "GOLDEN STANDARD FORMAT RULES:\n"
                "1. TITLE: Every criterion must have a ## header.\n"
                "2. LABELS: Provide justification and evidence in **Label:** format.\n"
                "3. SCORE: Specify the score as [PUAN: X].\n"
                "4. LANGUAGE: YOUR ENTIRE RESPONSE MUST BE IN TURKISH.\n\n"
                "## [Kriter Adı]\n"
                "- **Gerekçe:** ...\n"
                "- **Kanıt:** (Quote) (Kaynak: {filename})\n"
                "- **Puan:** [PUAN: X] (1-5)"
            )
            analiz_content = self.rubric_evaluator.run(analiz_prompt).content

            # 3. ADIM: DENETİMCİ KIYASLAMASI (Batch 2)
            denetim_prompt = (
                f"### CONTEXT DATA:\n{full_context}\n\n"
                f"### ANALYSIS RESULTS:\n{analiz_content}\n\n"
                "TASK: Audit and compare the analysis above.\n"
                "FORMAT RULES:\n"
                "1. HEADER: Use '### 🛡️ Denetim: [Criterion Name]'.\n"
                "2. COMPARISON: If there's a difference between Analysis Score and Audit Score, explain why based on evidence.\n"
                "3. MARKER: Place the final score in [DENETIM_PUANI: X] marker.\n"
                "4. LANGUAGE: YOUR ENTIRE RESPONSE MUST BE IN TURKISH.\n\n"
                "### 🛡️ Denetim: [Kriter Adı]\n"
                "- **Analiz Puanı:** [Score from analysis]\n"
                "- **Denetçi Puanı:** [Your score]\n"
                "- **Kıyaslama ve Gerekçe:** (Describe differences if any...)\n"
                "- **Karar:** [✅ ONAYLANDI / ❌ DÜZELTİLDİ]\n"
                "Nihai Puan Marker: [DENETIM_PUANI: X]"
            )
            denetim_content = self.rubric_validator.run(denetim_prompt).content

            # 4. TABLO VE BİRLEŞTİRME
            summary_rows = []
            for criterion_name in Config.RUBRIC_CRITERIA.keys():
                crit_escaped = re.escape(criterion_name)
                # Analizden puan çek (Regex fix)
                analiz_match = re.search(f"##.*?{crit_escaped}.*?PUAN:\s*(\d+)", analiz_content, re.DOTALL | re.IGNORECASE)
                a_score = analiz_match.group(1) if analiz_match else "—"
                
                # Denetimden puan çek
                denetim_block = re.search(f"Denetim:.*?{crit_escaped}.*?\n(.*?)(?=\n### 🛡️ Denetim|$)", denetim_content, re.DOTALL | re.IGNORECASE)
                if denetim_block:
                    block_text = denetim_block.group(1)
                    score_info = OutputValidator.validate_rubric_score(block_text)
                    d_score = f"{score_info['score']}" if score_info['valid'] else "—"
                    karar = "✅" if a_score == d_score else "❌"
                    summary_rows.append(f"| {criterion_name} | {a_score}/5 | {d_score}/5 | {karar} |")
                else:
                    summary_rows.append(f"| {criterion_name} | {a_score}/5 | — | ❓ |")

            summary_table = (
                f"\n\n## 📊 Analiz vs Denetçi Puan Tablosu: {filename}\n\n"
                f"| Kriter | Analiz Puanı | Denetçi Puanı | Karar |\n"
                f"| :--- | :---: | :---: | :---: |\n"
                + "\n".join(summary_rows)
            )

            report_block = (
                f"## 📄 Rapor: {filename}\n\n"
                f"## 🔍 1. DETAYLI ANALİZLER\n{analiz_content}\n\n"
                f"--- \n\n"
                f"## 🛡️ 2. DENETÇİ VE KIYASLAMA RAPORU\n{denetim_content}\n\n"
                f"{summary_table}"
            )

            overall_results.append(report_block)
            overall_results.append("\n---\n")

        return "\n\n".join(overall_results)
