"""
Tutarsızlık analizi için sahte veri (anket/metin) üreten ajan.
Seçilen rapor içeriğine dayanarak İKİ AYRI bölüm üretir:
  1. ANKET TABLOSU: Sorular + 1-5 puan + isaretleme (bazi dogru, bazi yanlis)
  2. METIN BEYANLARI: Paragraf halinde iddialar (bazi dogru, bazi yanlis)
Her iddia için ground truth etiketi üretir: [GT:DOGRU] veya [GT:YANLIS]
"""
from agno.agent import Agent
from agno.models.ollama import Ollama


def create_mock_generator(model: Ollama) -> Agent:
    return Agent(
        model=model,
        description=(
            "Your task: Generate realistic test data based on a report's content. "
            "This data will later be compared with the report for consistency analysis."
        ),
        instructions=[
            "You will receive a report content and a Generation Mode: Tutarli, Tutarsiz, or Karmasik.",
            "Your task is to generate TWO COMPLETELY SEPARATE sections.",
            "",
            "### SECTION 1: SURVEY TABLE (ANKET TABLOSU)",
            "Generate 5-7 measurable quality questions based on YOKAK criteria from the report.",
            "Each question gets a 1-5 score and a checkmark.",
            "MUST use this exact Markdown table format:",
            "",
            "## BOLUM 1: ANKET YANITLARI",
            "",
            "| # | Soru | Puan (1-5) | Isaretleme |",
            "| :-- | :--- | :---: | :---: |",
            "| 1 | [Concrete quality question — e.g.: Programlarin AKTS is yukleri belirlenmis mi?] | [1-5] | [X] or [ ] |",
            "",
            "SCORING RULES BY MODE:",
            "- TUTARSIZ mode: Give LOW scores (1-2) to things that are GOOD in report, HIGH scores (4-5) to what's WEAK.",
            "- TUTARLI mode: Give scores that accurately reflect the report's actual situation.",
            "- KARMASIK mode: Mix of correct and intentionally wrong scores.",
            "",
            "### SECTION 2: TEXT CLAIMS (METIN BEYANLARI)",
            "Write 4-6 claim sentences with concrete data (numbers, dates, unit names, activities).",
            "Write as PARAGRAPHS (not table).",
            "IMPORTANT: After each claim, add a ground truth tag on the same line: [GT:DOGRU] or [GT:YANLIS]",
            "",
            "## BOLUM 2: METIN BEYANLARI",
            "",
            "Example format:",
            "[Birim adi] bunyesinde [X adet] program bulunmakta olup, toplam [Y] ogrenci kayitlidir. [GT:DOGRU]",
            "[Z] adet TUBITAK projesi yurutulmektedir. [GT:YANLIS]",
            "",
            "TEXT RULES BY MODE:",
            "- TUTARSIZ mode: Use intentionally wrong numbers, wrong unit names, non-existent activities.",
            "- TUTARLI mode: All information matches the report exactly.",
            "- KARMASIK mode: Some sentences correct, some intentionally wrong.",
            "",
            "### CRITICAL RULES:",
            "1. SECTION 1 (Survey) and SECTION 2 (Text) MUST be SEPARATE — do NOT mix them.",
            "2. Survey MUST be in Markdown table format — NOT plain text.",
            "3. Text section MUST be in PARAGRAPH format — NOT table.",
            "4. Draw inspiration from the actual report content in both sections.",
            "5. Use the EXACT section headers: 'BOLUM 1: ANKET YANITLARI' and 'BOLUM 2: METIN BEYANLARI'.",
            "6. EVERY text claim MUST have a [GT:DOGRU] or [GT:YANLIS] tag at the end.",
        ],
    )
