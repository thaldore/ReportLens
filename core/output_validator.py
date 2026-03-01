"""
ReportLens Çıktı Doğrulama Modülü.
LLM çıktılarını kullanıcıya göstermeden önce doğrular:
- Halüsinasyon dedektörü (sayı eşleştirme)
- Format doğrulama (bölüm başlıkları)
- Tekrar dedektörü (paragraf benzerliği)
- Rubrik puan format doğrulama
"""
import re
from typing import Dict, List, Optional

from core.logging_config import get_logger

logger = get_logger(__name__)


class OutputValidator:
    """LLM çıktılarını doğrulayan post-processing katmanı."""

    # ── Halüsinasyon Dedektörü ────────────────────────────────────────

    @staticmethod
    def detect_hallucinated_numbers(output: str, context: str) -> Dict:
        """Çıktıdaki sayısal değerleri bağlamda arar.
        Bağlamda geçmeyen sayılar potansiyel halüsinasyondur.

        Returns:
            dict: {
                "verified": [bağlamda bulunan sayılar],
                "unverified": [bağlamda bulunamayan sayılar],
                "warning_count": int
            }
        """
        # Çıktıdaki anlamlı sayıları çıkar (2+ basamaklı, yüzde değerleri vb.)
        output_numbers = set(re.findall(r'\b(\d{2,}(?:[.,]\d+)?)\b', output))
        context_numbers = set(re.findall(r'\b(\d{2,}(?:[.,]\d+)?)\b', context))

        # Yıl, puan (1-5), sıra numaraları gibi genel sayıları hariç tut
        skip_patterns = {str(y) for y in range(2015, 2030)}  # Yıllar
        skip_patterns.update({'10', '20', '50', '100'})  # Yaygın yuvarlak sayılar

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

    # ── Format Doğrulama ──────────────────────────────────────────────

    @staticmethod
    def validate_sections(output: str, expected_sections: List[str]) -> Dict:
        """Beklenen bölüm başlıklarının var olduğunu kontrol eder.

        Returns:
            dict: {
                "found": [bulunan bölümler],
                "missing": [eksik bölümler],
                "compliance_rate": float (0-1)
            }
        """
        output_lower = output.lower()
        found = []
        missing = []

        for section in expected_sections:
            # Hem tam eşleşme hem de kısmi eşleşme dene
            if section.lower() in output_lower:
                found.append(section)
            else:
                # Bölüm numarası olmadan da ara
                section_clean = re.sub(r'^\d+\.\s*', '', section).strip()
                if section_clean.lower() in output_lower:
                    found.append(section)
                else:
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
        """Tekrarlı paragrafları tespit eder (Jaccard benzerliği ile).

        Returns:
            dict: {
                "duplicate_pairs": [(i, j, benzerlik)],
                "duplicate_count": int,
                "cleaned_output": str (tekrarlar kaldırılmış)
            }
        """
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
                    duplicates_to_remove.add(j)  # Sonraki tekrarı işaretle

        # Temizlenmiş çıktı oluştur
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
        """Rubrik puanının doğru formatta olup olmadığını kontrol eder.

        Returns:
            dict: {
                "score": int veya None,
                "valid": bool,
                "raw_match": str
            }
        """
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
        """Kanıt alıntısının bağlamda gerçekten geçip geçmediğini kontrol eder.

        Returns:
            dict: {
                "verified": bool,
                "match_ratio": float (0-1),
                "best_match": str
            }
        """
        if not evidence_quote or not context:
            return {"verified": False, "match_ratio": 0.0, "best_match": ""}

        # Alıntıdan kelime dizileri (n-gram) oluştur
        evidence_words = evidence_quote.lower().split()
        context_lower = context.lower()

        if len(evidence_words) < min_ngram:
            # Çok kısa alıntılar doğrudan ara
            return {
                "verified": evidence_quote.lower().strip("'\"") in context_lower,
                "match_ratio": 1.0 if evidence_quote.lower().strip("'\"") in context_lower else 0.0,
                "best_match": evidence_quote if evidence_quote.lower().strip("'\"") in context_lower else "",
            }

        # N-gram eşleştirme
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

    # ── Bütünleşik Doğrulama ─────────────────────────────────────────

    @staticmethod
    def validate_full_output(
        output: str,
        context: str,
        expected_sections: Optional[List[str]] = None,
        remove_duplicates: bool = True,
    ) -> str:
        """Tam doğrulama pipeline'ı: halüsinasyon + format + tekrar."""
        result = output

        # 1. Tekrar kaldırma
        if remove_duplicates:
            result = OutputValidator.remove_repetitions(result)

        # 2. Halüsinasyon uyarısı
        result = OutputValidator.add_hallucination_warnings(result, context)

        # 3. Format uyarısı
        if expected_sections:
            result = OutputValidator.add_missing_section_warnings(result, expected_sections)

        return result
