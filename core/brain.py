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
from core.output_validator import OutputValidator
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

    def analyze(self, query: str, birim: str = None, yil: str = None) -> tuple:
        """Genel rapor analizi. Sorguda birim/yıl otomatik tespit edilip filtrelenerek arama yapılır.
        Returns: (result_text, detected_birim, detected_yil) tuple.
        """
        # Kullanıcı belirtmediyse sorgudaki birim ve yılı otomatik tespit et
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

        birim_info = f"Birim filtresi: **{birim}**" if birim else "Birim filtresi yok (tüm raporlar)"
        yil_info = f", Yıl filtresi: **{yil}**" if yil else ""

        prompt = (
            f"[{birim_info}{yil_info}]\n"
            f"Context Data:\n{context}\n\n"
            f"Question/Task: {query}\n\n"
            "Answer the question based on the context data above. "
            "Use ONLY data from the specified unit and year. "
            "Include concrete numbers, dates, and activity names in your answer."
        )

        response = self.analyzer.run(prompt)
        result = OutputValidator.validate_full_output(
            response.content, context,
            expected_sections=["BULGULAR", "GÜÇLÜ YÖNLER", "GELİŞİME AÇIK"]
        )
        return result, auto_birim, auto_yil

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
            "IMPORTANT RULES:\n"
            "1. Each section MUST have at least 2-3 paragraphs with concrete data points.\n"
            "2. Transfer specific numbers, dates, and names from the analyses.\n"
            "3. Do NOT fabricate information not in the analyses.\n"
            "4. Write in YOKAK 7-section format.\n"
            "5. Do NOT give advice — report the current state only.\n"
            "6. Each section must contain at least 3 concrete data points.\n"
            "7. Do NOT repeat the same paragraph in multiple sections."
        )

        report = self.report_writer.run(report_prompt)
        # Post-processing: tekrar kaldırma + halüsinasyon uyarısı
        result = OutputValidator.remove_repetitions(report.content)
        result = OutputValidator.add_hallucination_warnings(result, combined)
        return result

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

        # Chunk'ları chunk_index'e göre sırala (rapor yapısı korunsun)
        sorted_results = sorted(search_results, key=lambda p: p.payload.get("chunk_index", 0))
        full_content = "\n\n".join([p.payload.get("content", "") for p in sorted_results])

        # Metadata'yı dosya adından al (tür, birim, yıl)
        metadata = VectorStore.parse_metadata(filename)
        meta_info = (
            f"Rapor Metadata:\n"
            f"- Birim: {metadata.get('birim', 'Bilinmiyor')}\n"
            f"- Yil: {metadata.get('yil', 'Bilinmiyor')}\n"
            f"- Tur: {metadata.get('tur', 'Bilinmiyor')}\n"
        )

        prompt = (
            f"File: {filename}\n"
            f"{meta_info}\n"
            f"Document Content:\n{full_content[:15000]}\n\n"
            "TASK: Analyze this report comprehensively in Turkish, using EXACTLY this structure.\n"
            "Use ONLY concrete data from the document. Fabricating numbers is STRICTLY FORBIDDEN.\n\n"
            f"## 1. Rapor Turu ve Kapsami\n"
            f"- Raporun turu: {metadata.get('tur', 'Bilinmiyor')}\n"
            f"- Birim: {metadata.get('birim', 'Bilinmiyor')}\n"
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
        # Post-processing: halüsinasyon uyarısı
        result = OutputValidator.validate_full_output(
            response.content, full_content,
            expected_sections=["Rapor Türü", "Sayısal Veriler", "Bulgular", "Güçlü Yönler", "Zayıf Yönler", "Eylem"]
        )
        return result

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
            # Chunk'ları chunk_index'e göre sırala
            sorted_results = sorted(search_results, key=lambda p: p.payload.get("chunk_index", 0))
            context = "\n".join([p.payload.get("content", "") for p in sorted_results])
        except Exception:
            context = self.vector_store.search("", filename=filename, k=15)

        if not context:
            return "Veri üretmek için rapor içeriği bulunamadı."
        
        prompt = (
            f"File: {filename}\n"
            f"Generation Mode: {mode}\n"
            f"Report Content:\n{context[:10000]}\n\n"
            "TASK: Generate 2 SEPARATE sections based on the report content above.\n"
            "1. BOLUM 1: ANKET YANITLARI — Markdown table format (5-7 questions, 1-5 score, checkmark)\n"
            "2. BOLUM 2: METIN BEYANLARI — Paragraph claims (4-6 sentences) with [GT:DOGRU] or [GT:YANLIS] tags\n"
            "Follow your instruction format EXACTLY. Do NOT change section headers."
        )
        response = self.mock_generator.run(prompt)
        return response.content

    # ── Tutarsızlık Analizi ───────────────────────────────────────────

    def check_consistency(
        self,
        comparison_text: str,
        survey_text: str = None,
        birim: str = None,
        filename: str = None,
    ) -> str:
        """Rapor içeriği ile metin/anket karşılaştırması yapar.
        survey_text: Ayrı bir text area'dan gelen anket verileri (opsiyonel).
        """
        try:
            # Beyan boyutu sınırlama
            comparison_text = comparison_text[:Config.MAX_COMPARISON_TEXT]
            if survey_text:
                survey_text = survey_text[:Config.MAX_COMPARISON_TEXT]

            if filename:
                # Sadece belirli bir raporla kıyasla
                try:
                    search_results = self.vector_store.client.scroll(
                        collection_name=self.vector_store.collection_name,
                        scroll_filter=Filter(
                            must=[FieldCondition(key="dosya_adi", match=MatchValue(value=filename))]
                        ),
                        limit=Config.MAX_CONTEXT_CHUNKS,
                        with_payload=True
                    )[0]
                    # Chunk'ları chunk_index'e göre sırala
                    sorted_results = sorted(search_results, key=lambda p: p.payload.get("chunk_index", 0))
                    context = "\n\n".join([p.payload.get("content", "") for p in sorted_results])
                except Exception as e:
                    logger.warning(f"Scroll hatası, search'e dönülüyor: {str(e)}")
                    context = self.vector_store.search("", k=Config.MAX_CONTEXT_CHUNKS, filename=filename)
            else:
                # Genel arama — beyan metninden birim tespit et
                if birim is None:
                    birim = self._detect_birim_from_query(comparison_text)
                context = self.vector_store.search(comparison_text[:500], birim=birim, k=Config.MAX_CONTEXT_CHUNKS)

            if not context or "hata" in str(context).lower():
                return "Karşılaştırma için yeterli rapor verisi bulunamadı."

            # Kullanıcı beyanlarını birleştir (metin + anket ayrı başlıklarla)
            user_claims = ""
            if survey_text:
                user_claims += f"### ANKET VERILERI:\n{survey_text}\n\n"
            user_claims += f"### METIN BEYANLARI:\n{comparison_text}"

            prompt = (
                f"## 1. REPORT CONTENT (ABSOLUTE TRUTH — every piece of information here is factual):\n"
                f"{context[:12000]}\n\n"
                f"## 2. USER CLAIMS (test the accuracy of these):\n"
                f"{user_claims}\n\n"
                "TASK: Analyze EACH claim and survey answer SEPARATELY.\n"
                "Label each: DOGRU / YANLIS / BILGI YOK with confidence level (HIGH/MEDIUM/LOW).\n"
                "The REPORT is ABSOLUTE TRUTH — never question report information.\n"
                "Follow your instruction format: ANALIZ 1, ANALIZ 2, ANALIZ 3, OZET TABLOSU."
            )
            response = self.consistency_checker.run(prompt)
            # Post-processing
            result = OutputValidator.validate_full_output(
                response.content, context,
                expected_sections=["ANALIZ 1", "ANALIZ 2", "ANALIZ 3", "ÖZET TABLOSU"]
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
                    f"Report: {filename}\n"
                    f"Criterion: {criterion_name} — {criterion_desc}\n\n"
                    f"CONTEXT (Text from this file ONLY):\n{context}\n\n"
                    "TASK: Score this criterion 1-5 based on the context above.\n"
                    "Write ONLY these 4 lines:\n"
                    "Puan: [1-5 INTEGER]/5\n"
                    "Gerekce: [why this score]\n"
                    "Kanit: '[exact quote from context]'\n"
                    "Gelisim Onerisi: [concrete step]\n\n"
                    "REMEMBER: Most scores should be 2-3. Give 4-5 ONLY with concrete PDCA evidence."
                )
                eval_response = self.rubric_evaluator.run(eval_prompt)
                eval_content = eval_response.content

                # Evaluator çıktısından puan çıkar
                eval_score = OutputValidator.validate_rubric_score(eval_content)
                puan_str = f"{eval_score['score']}/5" if eval_score['valid'] else "Değerlendirilemedi"

                # Kanıt doğrulama (n-gram matching)
                kanit_match = re.search(r"Kanit:\s*['\"](.+?)['\"]" , eval_content)
                evidence_note = ""
                if kanit_match:
                    evidence_text = kanit_match.group(1)
                    ev_result = OutputValidator.verify_evidence(evidence_text, context)
                    if not ev_result["verified"]:
                        evidence_note = "\n⚠️ Kanıt alıntısı bağlamda doğrulanamadı."

                # 2. Adım: Denetleme — BLIND REVIEW (evaluator puanını gösterme)
                val_prompt = (
                    f"Report: {filename}\n"
                    f"Criterion: {criterion_name} — {criterion_desc}\n\n"
                    f"CONTEXT (Original Report Text):\n{context}\n\n"
                    "STEP 1: Score this criterion INDEPENDENTLY (1-5) using only the context.\n"
                    "STEP 2: The other evaluator's assessment is below. Compare your score with theirs.\n\n"
                    f"OTHER EVALUATOR'S ASSESSMENT:\n{eval_content}\n\n"
                    "Write ONLY these 4 lines in Turkish:\n"
                    "Bagimsiz Puan: [1-5]/5\n"
                    "Karar: ONAYLANDI veya HATALI BULUNDU\n"
                    "Gozlem: [max 3 sentences]\n"
                    "Sonuc: Puan [X]/5 olmalidir — [brief reason]"
                )
                val_response = self.rubric_validator.run(val_prompt)
                val_content = val_response.content

                # Denetçi bağımsız puanını çıkar
                val_score = OutputValidator.validate_rubric_score(val_content)
                val_puan_str = f"{val_score['score']}/5" if val_score['valid'] else "—"

                # Denetim kararını özet için çıkar
                _vc_lower = val_content.lower()
                _approved = any(kw in _vc_lower for kw in [
                    "onaylandi", "onaylandı", "dogrudur", "doğrudur", "✅ onaylandi",
                    "tutarli", "tutarlı", "dogru bulundu", "doğru bulundu",
                ])
                karar = "✅ Onay" if _approved else "❌ Düzeltme"
                summary_rows.append(f"| {criterion_name} | {puan_str} | {val_puan_str} | {karar} |")
                
                # Kriter bazlı birleştirme
                criterion_result = (
                    f"### 📏 {criterion_name}\n"
                    f"{eval_content}{evidence_note}\n\n"
                    f"#### 🛡️ DENETİM (Blind Review)\n"
                    f"{val_content}\n"
                    f"{'-' * 40}"
                )
                report_analyses.append(criterion_result)

            # Özet tablo (güncellenmiş: denetçi puanı da gösterilir)
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
