"""
ReportLens Çıktı Doğrulama Modülü.
LLM çıktılarını kullanıcıya göstermeden önce doğrular:
- Halüsinasyon dedektörü (sayı eşleştirme)
- Format doğrulama (accent-insensitive bölüm başlıkları)
- Tekrar dedektörü (paragraf benzerliği)
- Rubrik puan format doğrulama
- Structured JSON output parser
- Birim kısaltma doğrulama
"""
import json
import re
import unicodedata
from typing import Any, Dict, List, Optional

from core.logging_config import get_logger

logger = get_logger(__name__)


class OutputValidator:
    """LLM çıktılarını doğrulayan post-processing katmanı."""

    # ── Türkçe Karakter Normalize ─────────────────────────────────────

    # Türkçe → ASCII eşleşme tablosu
    _TR_MAP = str.maketrans(
        "çğıöşüÇĞİÖŞÜâîûÂÎÛ",
        "cgiosuCGIOSUaiuAIU",
    )

    @staticmethod
    def normalize_turkish(text: str) -> str:
        """Türkçe karakterleri ASCII karşılıklarına dönüştürür.
        GÜÇLÜ YÖNLER → GUCLU YONLER
        """
        return text.translate(OutputValidator._TR_MAP)

    # ── Halüsinasyon Dedektörü ────────────────────────────────────────

    @staticmethod
    def detect_hallucinated_numbers(output: str, context: str) -> Dict:
        """Çıktıdaki sayısal değerleri bağlamda arar.
        Bağlamda geçmeyen sayılar potansiyel halüsinasyondur.
        """
        output_numbers = set(re.findall(r'\b(\d{2,}(?:[.,]\d+)?)\b', output))
        context_numbers = set(re.findall(r'\b(\d{2,}(?:[.,]\d+)?)\b', context))

        # Yaygın genel sayıları hariç tut
        skip_patterns = {str(y) for y in range(2015, 2030)}
        skip_patterns.update({'10', '20', '50', '100'})

        verified = []
        unverified = []

        for num in output_numbers:
            if num in skip_patterns:
                continue
            if num in context_numbers:
                verified.append(num)
            else:
                unverified.append(num)

        if unverified:
            logger.warning(
                f"Halüsinasyon uyarısı: {len(unverified)} doğrulanmamış sayı: {unverified[:5]}"
            )

        return {
            "verified": verified,
            "unverified": unverified,
            "warning_count": len(unverified),
        }

    @staticmethod
    def add_hallucination_warnings(output: str, context: str) -> str:
        """Doğrulanmamış sayılar varsa çıktının sonuna uyarı ekler."""
        result = OutputValidator.detect_hallucinated_numbers(output, context)

        if result["warning_count"] > 0:
            warning = (
                f"\n\n---\n⚠️ **Doğrulama Notu:** Çıktıda {result['warning_count']} adet "
                f"bağlamda doğrulanamayan sayısal veri tespit edildi. "
                f"Bu değerler modelin ürettiği tahminler olabilir. "
                f"Doğrulanmamış değerler: {', '.join(result['unverified'][:10])}"
            )
            return output + warning

        return output

    # ── Format Doğrulama (Accent-Insensitive) ─────────────────────────

    @staticmethod
    def validate_sections(output: str, expected_sections: List[str]) -> Dict:
        """Beklenen bölüm başlıklarının var olduğunu kontrol eder.
        Accent-insensitive ve case-insensitive eşleşme kullanır.
        """
        output_normalized = OutputValidator.normalize_turkish(output).lower()
        found = []
        missing = []

        for section in expected_sections:
            section_normalized = OutputValidator.normalize_turkish(section).lower()
            # 1. Tam eşleşme (normalized)
            if section_normalized in output_normalized:
                found.append(section)
                continue
            # 2. Numarasız eşleşme
            section_clean = re.sub(r'^\d+\.\s*', '', section_normalized).strip()
            if section_clean in output_normalized:
                found.append(section)
                continue
            # 3. Anahtar kelime eşleşme (başlığın %60+ kelimesi bulunursa)
            words = [w for w in section_clean.split() if len(w) > 2]
            if words:
                matched = sum(1 for w in words if w in output_normalized)
                if matched / len(words) >= 0.6:
                    found.append(section)
                    continue
            missing.append(section)

        total = len(expected_sections)
        compliance = len(found) / total if total > 0 else 0.0

        if missing:
            logger.info(f"Format uyarısı: {len(missing)} eksik bölüm: {missing}")

        return {
            "found": found,
            "missing": missing,
            "compliance_rate": round(compliance, 2),
        }

    @staticmethod
    def add_missing_section_warnings(output: str, expected_sections: List[str]) -> str:
        """Eksik bölümler varsa çıktının sonuna uyarı ekler."""
        result = OutputValidator.validate_sections(output, expected_sections)

        if result["missing"]:
            warning = (
                f"\n\n---\n⚠️ **Format Notu:** Beklenen {len(expected_sections)} bölümden "
                f"{len(result['missing'])} tanesi çıktıda bulunamadı: "
                f"{', '.join(result['missing'][:5])}"
            )
            return output + warning

        return output

    # ── Tekrar Dedektörü ──────────────────────────────────────────────

    @staticmethod
    def detect_repetitions(output: str, threshold: float = 0.8) -> Dict:
        """Tekrarlı paragrafları tespit eder (Jaccard benzerliği ile)."""
        paragraphs = [p.strip() for p in output.split('\n\n') if len(p.strip()) > 50]
        duplicate_pairs = []
        duplicates_to_remove = set()

        for i in range(len(paragraphs)):
            for j in range(i + 1, len(paragraphs)):
                similarity = OutputValidator._jaccard_similarity(
                    paragraphs[i], paragraphs[j]
                )
                if similarity >= threshold:
                    duplicate_pairs.append((i, j, round(similarity, 2)))
                    duplicates_to_remove.add(j)

        cleaned_paragraphs = [
            p for idx, p in enumerate(paragraphs)
            if idx not in duplicates_to_remove
        ]

        if duplicate_pairs:
            logger.info(f"Tekrar tespit: {len(duplicate_pairs)} tekrarlı paragraf çifti")

        return {
            "duplicate_pairs": duplicate_pairs,
            "duplicate_count": len(duplicate_pairs),
            "cleaned_output": '\n\n'.join(cleaned_paragraphs),
        }

    @staticmethod
    def remove_repetitions(output: str, threshold: float = 0.8) -> str:
        """Tekrarlı paragrafları kaldırır."""
        result = OutputValidator.detect_repetitions(output, threshold)
        if result["duplicate_count"] > 0:
            return result["cleaned_output"]
        return output

    @staticmethod
    def _jaccard_similarity(text1: str, text2: str) -> float:
        """İki metin arasındaki Jaccard benzerliğini hesaplar."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        if not words1 or not words2:
            return 0.0
        intersection = words1 & words2
        union = words1 | words2
        return len(intersection) / len(union)

    # ── Rubrik Puan Doğrulama ─────────────────────────────────────────

    @staticmethod
    def validate_rubric_score(output: str) -> Dict:
        """Rubrik puanının doğru formatta olup olmadığını kontrol eder."""
        puan_patterns = [
            r'[Pp]uan\s*[:\-]?\s*(\d)\s*/\s*5',
            r'[Pp]uan\s*[:\-]?\s*(\d)\b',
            r'\b(\d)\s*/\s*5\b',
        ]

        for pattern in puan_patterns:
            match = re.search(pattern, output)
            if match:
                val = int(match.group(1))
                if 1 <= val <= 5:
                    return {
                        "score": val,
                        "valid": True,
                        "raw_match": match.group(0),
                    }

        return {"score": None, "valid": False, "raw_match": ""}

    @staticmethod
    def enforce_rubric_score(output: str) -> str:
        """Puan bulunamazsa 'Değerlendirilemedi' mesajı ekler."""
        result = OutputValidator.validate_rubric_score(output)
        if not result["valid"]:
            return output + "\n\n⚠️ **Puan parse edilemedi.** Bu kriter için değerlendirme tamamlanamadı."
        return output

    # ── Kanıt Doğrulama (N-gram Matching) ─────────────────────────────

    @staticmethod
    def verify_evidence(evidence_quote: str, context: str, min_ngram: int = 3) -> Dict:
        """Kanıt alıntısının bağlamda gerçekten geçip geçmediğini kontrol eder."""
        if not evidence_quote or not context:
            return {"verified": False, "match_ratio": 0.0, "best_match": ""}

        evidence_words = evidence_quote.lower().split()
        context_lower = context.lower()

        if len(evidence_words) < min_ngram:
            found = evidence_quote.lower().strip("'\"") in context_lower
            return {
                "verified": found,
                "match_ratio": 1.0 if found else 0.0,
                "best_match": evidence_quote if found else "",
            }

        matched_ngrams = 0
        total_ngrams = max(1, len(evidence_words) - min_ngram + 1)

        for i in range(total_ngrams):
            ngram = ' '.join(evidence_words[i:i + min_ngram])
            if ngram in context_lower:
                matched_ngrams += 1

        match_ratio = matched_ngrams / total_ngrams

        return {
            "verified": match_ratio >= 0.5,
            "match_ratio": round(match_ratio, 2),
            "best_match": "",
        }

    # ── Structured JSON Output Parser ─────────────────────────────────

    @staticmethod
    def parse_json_output(output: str) -> Optional[Dict[str, Any]]:
        """LLM çıktısından JSON bloğu çıkarır ve parse eder.
        ```json ... ``` blokları veya düz JSON destekler.
        """
        # 1. Markdown JSON bloğunu ara
        json_block = re.search(r'```json\s*\n?(.*?)\n?\s*```', output, re.DOTALL)
        if json_block:
            try:
                return json.loads(json_block.group(1).strip())
            except json.JSONDecodeError:
                pass

        # 2. Düz JSON ara (ilk { ... } eşleşmesi)
        brace_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', output, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("JSON parse edilemedi — düz metin çıktı olarak işlenecek.")
        return None

    @staticmethod
    def extract_sections_as_dict(output: str) -> Dict[str, str]:
        """Markdown çıktısındaki ## başlıklarını sözlüğe dönüştürür.
        '## 2. TEMEL BULGULAR\nİçerik...' → {'TEMEL BULGULAR': 'İçerik...'}
        """
        sections = {}
        current_title = None
        current_content = []

        for line in output.split('\n'):
            heading_match = re.match(r'^#{1,3}\s*\d*\.?\s*(.+)$', line.strip())
            if heading_match:
                if current_title:
                    sections[current_title] = '\n'.join(current_content).strip()
                current_title = heading_match.group(1).strip()
                current_content = []
            elif current_title is not None:
                current_content.append(line)

        if current_title:
            sections[current_title] = '\n'.join(current_content).strip()

        return sections

    # ── Birim Kısaltma Doğrulama ──────────────────────────────────────

    @staticmethod
    def validate_birim_name(output: str, expected_birim: str = None) -> Dict:
        """Çıktıdaki birim adının doğru olup olmadığını kontrol eder.
        IIBF ≠ 'İleri Teknoloji Bilişim Fakültesi' gibi halüsinasyonları tespit eder.
        """
        from core.config import Config

        wrong_names = []
        if expected_birim and expected_birim in Config.BIRIM_FULL_NAMES:
            correct_name = Config.BIRIM_FULL_NAMES[expected_birim]
            # Bilinen yanlış adları kontrol et
            known_wrong = {
                "IIBF": [
                    "İstatistik ve İnovasyon", "İç ve Dış İlişkiler",
                    "İleri Teknoloji Bilişim", "İnsan ve İletişim",
                ],
                "ITBF": [
                    "İdari Bilgi Sistemleri", "İleri Teknoloji Bilişim",
                    "İletişim ve Toplum Bilimleri",
                ],
            }
            for wrong in known_wrong.get(expected_birim, []):
                if wrong.lower() in output.lower():
                    wrong_names.append(wrong)

        return {
            "has_wrong_names": len(wrong_names) > 0,
            "wrong_names": wrong_names,
            "correct_name": Config.BIRIM_FULL_NAMES.get(expected_birim, expected_birim),
        }

    @staticmethod
    def fix_birim_names(output: str, expected_birim: str) -> str:
        """Yanlış birim adlarını doğru olanlarla değiştirir."""
        result = OutputValidator.validate_birim_name(output, expected_birim)
        if result["has_wrong_names"]:
            for wrong in result["wrong_names"]:
                output = output.replace(wrong, result["correct_name"])
            logger.info(
                f"Birim adı düzeltildi: {result['wrong_names']} → {result['correct_name']}"
            )
        return output

    # ── Bütünleşik Doğrulama ─────────────────────────────────────────

    @staticmethod
    def validate_full_output(
        output: str,
        context: str,
        expected_sections: Optional[List[str]] = None,
        remove_duplicates: bool = True,
        expected_birim: str = None,
    ) -> str:
        """Tam doğrulama pipeline'ı: halüsinasyon + format + tekrar + birim."""
        result = output

        # 1. Tekrar kaldırma
        if remove_duplicates:
            result = OutputValidator.remove_repetitions(result)

        # 2. Birim adı düzeltme
        if expected_birim:
            result = OutputValidator.fix_birim_names(result, expected_birim)

        # 3. Halüsinasyon uyarısı
        result = OutputValidator.add_hallucination_warnings(result, context)

        # 4. Format uyarısı
        if expected_sections:
            result = OutputValidator.add_missing_section_warnings(result, expected_sections)

        return result
