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

        context = self.vector_store.search(query, birim=birim, yil=yil)

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
            f"[{birim_info}{yil_info}]\n"
            f"Context Data:\n{context}\n\n"
            f"Question/Task: {query}\n\n"
            "Answer the question based on the context data above. "
            "Use ONLY data from the specified unit and year. "
            "Include concrete numbers, dates, and activity names in your answer. "
            "If a number is NOT in the context, write 'Raporda bu veri bulunamamistir.'"
        )

        response = self.analyzer.run(prompt)
        result = OutputValidator.validate_full_output(
            response.content, context,
            expected_sections=["BULGULAR", "GUCLU YONLER", "GELISIME ACIK"],
            expected_birim=birim,
        )
        return result, auto_birim, auto_yil

    # ── Öz Değerlendirme Raporu ───────────────────────────────────────

    def generate_self_evaluation(self, birim: str, yil: str = None) -> str:
        """Birden fazla kalite raporundan öz değerlendirme raporu üretir.
        Multi-step LLM: Her kriter ayrı çağrı + birleştirme.
        """
        birim_full = self._get_birim_full_name(birim)
        
        # 1. Her kriteri paralel analiz et (Analyzer)
        from concurrent.futures import ThreadPoolExecutor, as_completed
        criterion_data = list(Config.RUBRIC_CRITERIA.items())
        criteria_analyses = [None] * len(criterion_data) # Sırayı korumak için
        
        def process_criterion_eval(c_idx, c_id, c_desc):
            logger.info(f"  ⏳ Kriter analiz ediliyor: {c_id}")
            context = self.vector_store.search(
                f"{c_id} {c_desc}", 
                birim=birim, 
                yil=yil, 
                k=Config.MAX_CONTEXT_CHUNKS
            )
            
            prompt = (
                f"Birim: {birim_full} ({birim})\nYıl: {yil if yil else 'Tümü'}\n"
                f"Kalite Kriteri: {c_id}\n"
                f"Veri Bağlamı:\n{context}\n\n"
                "GÖREV: Bu kriter için Güçlü Yanlar ve Gelişim Alanlarını analiz et. "
                "MUTLAKA somut bir veri veya rapor alıntısı ekle."
            )
            response = self.analyzer.run(prompt)
            return c_idx, f"### {c_id}\n{response.content[:2500]}"

        with ThreadPoolExecutor(max_workers=len(criterion_data)) as executor:
            futures = [executor.submit(process_criterion_eval, i, cid, desc) for i, (cid, desc) in enumerate(criterion_data)]
            for future in as_completed(futures):
                idx, content = future.result()
                criteria_analyses[idx] = content

        # 2. Sentez Raporu Oluştur (Sıralı - Donma Riskine Karşı Güvenli Mod)
        logger.info(f"  📝 {birim} için rapor sentezleniyor...")
        full_context = "\n\n".join([c for c in criteria_analyses if c])
        
        # Section talimatları
        sections = ["Yonetici Ozeti", "Liderlik", "Egitim", "Arastirma", "Toplumsal Katki", "Guclu Yonler", "Sonuc"]
        report_prompt = (
            f"Birim: {birim_full} ({birim})\nYıl: {yil if yil else 'Tümü'}\n\n"
            f"KRİTER ANALİZLERİ:\n{full_context}\n\n"
            "GÖREV: Yukarıdaki analizleri kullanarak resmi YÖKAK formatında tek parçalık bir Öz Değerlendirme Raporu oluştur.\n"
            "Aşağıdaki başlıkları kullan:\n"
            + ", ".join([f"## {s}" for s in sections])
        )
        response = self.report_writer.run(report_prompt)
        
        # 3. Doğrulama ve Temizlik
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
        search_results = self.vector_store.get_file_content(filename)

        if not search_results:
            return f"{filename} için veritabanında kayıt bulunamadı."

        full_content = "\n\n".join([p.get("content", "") for p in search_results])



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
            f"File: {filename}\n"
            f"{meta_info}\n"
            f"Document Content:\n{full_content[:15000]}\n\n"
            "TASK: Analyze this report comprehensively in Turkish, using EXACTLY this structure.\n"
            "Use ONLY concrete data from the document. Fabricating numbers is STRICTLY FORBIDDEN.\n"
            "If a number does NOT appear in the document, write 'Raporda bu veri bulunamamistir.'\n\n"
            f"## 1. Rapor Turu ve Kapsami\n"
            f"- Raporun turu: {metadata.get('tur', 'Bilinmiyor')}\n"
            f"- Birim: {birim_full}\n"
            f"- Yil: {metadata.get('yil', 'Bilinmiyor')}\n\n"
            "## 2. Temel Sayisal Veriler\n"
            "- Student counts, program counts, project/publication counts, survey results\n"
            "- Use EXACT numbers from the report. If data not found, write 'Raporda bu veri bulunamamistir'\n\n"
            "## 3. Ana Bulgular\n"
            "- Top 4-5 findings with concrete evidence\n\n"
            "## 4. Guclu Yonler\n"
            "- Positive areas with evidence from report\n\n"
            "## 5. Zayif Yonler / Gelisim Alanlari\n"
            "- Weak or missing areas\n\n"
            "## 6. Eylem / Hedefler\n"
            "- Goals and actions mentioned in the report\n\n"
            "Base your analysis ONLY on the document content above."
        )

        response = self.analyzer.run(prompt)
        result = OutputValidator.validate_full_output(
            response.content, full_content,
            expected_sections=["Rapor Turu", "Sayisal Veriler", "Bulgular", "Guclu Yonler", "Zayif Yonler", "Eylem"],
            expected_birim=birim,
        )
        return result

    # ── Sahte Veri Üretimi ──────────────────────────────────────────────

    def generate_mock_data(self, filename: str, mode: str = "Tutarsız") -> str:
        """Seçilen rapor için hem Anket hem Metin içeren hibrit sahte veri üretir.
        Fallback mekanizması: BOLUM bölümleri bulunamazsa yeniden dener.
        """
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
            "(Generate 4-6 sentences of claims/paragraphs with [GT:DOGRU] or [GT:YANLIS] tags at the end of each claim)\n\n"
            "CRITICAL: Start the first block with [ANKET_VERISI] and the second with [METIN_BEYANLARI]. Do NOT mix them."
        )

        # İlk deneme
        response = self.mock_generator.run(prompt)
        result = response.content

        # Basit Kontrol
        if "[ANKET_VERISI]" not in result or "[METIN_BEYANLARI]" not in result:
            logger.warning("Mock veri ayırıcıları bulunamadı, daha zorlayıcı prompt ile deneniyor...")
            retry_prompt = prompt + "\n\nIMPORTANT: You MUST use the [ANKET_VERISI] and [METIN_BEYANLARI] tags as headers."
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

            # Dosya bazlı semantik arama (RAG) — "BİLGİ YOK" sorununu çözmek için
            if filename:
                # Kullanıcının beyanlarını sorgu olarak kullan (En alakalı parçaları bul)
                search_query = f"{comparison_text[:1000]} {survey_text[:500] if survey_text else ''}"
                context = self.vector_store.search(search_query, k=15, filename=filename)
            else:
                if birim is None:
                    birim = self._detect_birim_from_query(comparison_text)
                context = self.vector_store.search(comparison_text[:500], birim=birim, k=15)

            if not context or not self._is_valid_context(context):
                return "Karşılaştırma için yeterli rapor verisi bulunamadı."

            # Kullanıcı beyanlarını birleştir
            user_claims = ""
            if survey_text:
                user_claims += f"### ANKET VERILERI:\n{survey_text}\n\n"
            user_claims += f"### METIN BEYANLARI:\n{comparison_text}"

            prompt = (
                f"## 1. RAPOR İÇERİĞİ (MUTLAK DOĞRU):\n{context[:12000]}\n\n"
                f"## 2. KULLANICI BEYANLARI:\n{user_claims}\n\n"
                "GÖREV: Her bir beyanı raporla kıyasla. DOĞRU/YANLIŞ/BİLGİ YOK olarak etiketle.\n"
                "ZORUNLU FORMAT: Aşağıdaki bölümlerin TAMAMI çıktıda bulunmalıdır:\n"
                "ANALIZ 1, ANALIZ 2, ANALIZ 3 ... (beyan sayısı kadar) ve en sonda MUTLAKA '### OZET TABLOSU'.\n"
                "Eğer veri yoksa bile 'Veri bulunamadı' yazarak tabloyu oluşturun."
            )
            response = self.consistency_checker.run(prompt)
            result = OutputValidator.validate_full_output(
                response.content, context,
                expected_sections=["ANALIZ 1", "ANALIZ 2", "ANALIZ 3", "OZET TABLOSU"]
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
        error_markers = [
            "sorun oluştu", "hata", "bulunamadı", "error", "no such attribute",
            "MSSQL", "arama hatası", "kritik arama"

        ]
        lower = context.lower()
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
            metadata = VectorStore.parse_metadata(filename)
            birim = metadata.get("birim", "")
            birim_full = self._get_birim_full_name(birim)
            
            report_analyses = []
            summary_rows = []

            for criterion_name, criterion_desc in Config.RUBRIC_CRITERIA.items():
                logger.info(f"  📏 Rubrik Değerlendirmesi: {filename} -> {criterion_name}")
                
            def process_criterion(criterion_name, criterion_desc):
                search_query = f"{criterion_name} {criterion_desc}"
                context = self.vector_store.search(
                    search_query, k=15, filename=filename,
                )

                if not self._is_valid_context(context):
                    return {
                        "type": "error",
                        "name": criterion_name,
                        "content": (
                            f"### 📏 {criterion_name}\n\n"
                            f"⚠️ Bu dosya için kriter bağlamı bulunamadı. "
                            f"Raporun bu bölümü eksik veya indekslenmemiş olabilir.\n\n"
                            f"**--- 🤖 RUBRİK DENETİMİ ---**\n"
                            f"Değerlendirme yapılamadı (bağlam yok).\n"
                            f"{'-' * 40}"
                        ),
                        "summary": f"| {criterion_name} | —/5 | ⚠️ Bağlam Yok |"
                    }

                # TEK AŞAMALI ENTEGRE ANALİZ (Değerlendirici + Denetçi)
                # Bağlam kaybını önlemek ve hızı artırmak için tek prompt
                master_prompt = (
                    f"### RAPOR: {filename}\n"
                    f"### KRİTER: {criterion_name}\n"
                    f"### KRİTER TANIMI: {criterion_desc}\n\n"
                    f"### BAĞLAM (RAPOR İÇERİĞİ):\n{context}\n\n"
                    f"GÖREV: Yukarıdaki bağlamı {criterion_name} kriterine göre analiz et.\n"
                    f"1. ADIM: Rapordan somut kanıtlar (sayfa/bölüm atfıyla) sunarak detaylı bir analiz yaz.\n"
                    f"2. ADIM: Bu analizi kendi içinde denetle (otokontrol).\n"
                    f"3. ADIM: Sonunda MUTLAKA şu marker'ları kullanarak puan ver:\n"
                    f"[PUAN: X] (1-5 arası analiz puanı)\n"
                    f"[DENETIM_PUANI: X] (1-5 arası denetim puanı)\n\n"
                    f"ÖNEMLİ: Çıktı profesyonel akademik bir dille ve TÜRKÇE olmalıdır."
                )

                response = self.rubric_evaluator.run(master_prompt)
                content = response.content
                
                # Puanları Ayıkla
                eval_score = OutputValidator.validate_rubric_score(content)
                puan_str = f"{eval_score['score']}/5" if eval_score['valid'] else "Değerlendirilemedi"
                
                # Denetim skoru (Marker'dan ayıkla)
                import re
                d_match = re.search(r'\[DENET[İI]M[_\s]PUANI:\s*([1-5])\]', content, re.IGNORECASE)
                val_puan_str = f"{d_match.group(1)}/5" if d_match else "—"
                
                # Karar
                karar = "✅ Onay" if eval_score['valid'] and int(eval_score['score']) >= 3 else "⚠️ İyileştirilmeli"

                return {
                    "type": "result",
                    "name": criterion_name,
                    "content": (
                        f"### 📏 {criterion_name}\n"
                        f"{content}\n"
                        f"{'-' * 40}"
                    ),
                    "summary": f"| {criterion_name} | {puan_str} | {val_puan_str} | {karar} |"
                }

            # Kriterleri paralel işlet
            from concurrent.futures import ThreadPoolExecutor, as_completed
            criterion_data = list(Config.RUBRIC_CRITERIA.items())
            # Sırayı korumak için listeleri önceden hazırlıyoruz
            report_analyses_ordered = [None] * len(criterion_data)
            summary_rows_ordered = [None] * len(criterion_data)

            # GPU VRAM koruması için worker sayısını 2 ile sınırlıyoruz
            with ThreadPoolExecutor(max_workers=min(2, len(criterion_data))) as executor:
                futures = {
                    executor.submit(process_criterion, name, desc): i 
                    for i, (name, desc) in enumerate(Config.RUBRIC_CRITERIA.items())
                }
                for future in as_completed(futures):
                    idx = futures[future]
                    res = future.result()
                    report_analyses_ordered[idx] = res["content"]
                    summary_rows_ordered[idx] = res["summary"]

            # Sonuçları listeye aktar
            report_analyses = [r for r in report_analyses_ordered if r]
            summary_rows = [s for s in summary_rows_ordered if s]

            # Özet tablo ve sonuç birleştirme
            summary_table = (
                f"\n\n### 📋 {filename} — Özet Puan Tablosu\n\n"
                f"| Kriter | Değerlendirici Puanı | Denetçi Puanı | Denetim Kararı |\n"
                f"| :--- | :---: | :---: | :---: |\n"
                + "\n".join(summary_rows)
            )

            overall_results.append("\n\n---\n\n".join(report_analyses))
            overall_results.append(summary_table)
            overall_results.append("\n---")


        return "\n\n".join(overall_results)
