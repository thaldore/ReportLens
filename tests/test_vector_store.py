"""
VectorStore testleri.
Not: Bu testler Ollama + Qdrant gerektirdiğinden, tam entegrasyon testleri için
bu servislerin çalışıyor olması gerekir. Birim testleri metadata parsing üzerinden yapılır.
"""
import pytest

from core.vector_store import VectorStore


class TestMetadataParsing:
    """Metadata çıkarma testleri (servis bağımsız)."""

    def test_fen_fakültesi(self):
        meta = VectorStore.parse_metadata("Fen_2024_Oz_Degerlendirme_Raporu.md")
        assert meta["birim"] == "Fen"
        assert meta["yil"] == "2024"
        assert meta["tur"] == "Oz_Degerlendirme_Raporu"

    def test_iibf_eylem_plani(self):
        meta = VectorStore.parse_metadata("IIBF_2023_Eylem_Plani_Izleme_Raporu.md")
        assert meta["birim"] == "IIBF"
        assert meta["yil"] == "2023"

    def test_itbf_akran(self):
        meta = VectorStore.parse_metadata("ITBF_2024_Cografya_Akran.md")
        assert meta["birim"] == "ITBF"
        assert meta["yil"] == "2024"
        assert meta["tur"] == "Cografya_Akran"

    def test_mimarlik_raporu(self):
        meta = VectorStore.parse_metadata("Mimarlik_2025_Oz_Degerlendirme_Raporu.md")
        assert meta["birim"] == "Mimarlik"
        assert meta["yil"] == "2025"

    def test_dosya_adi_korunur(self):
        fname = "IIBF_2024_Mezun_Anketi_Degerlendirme_Raporu.md"
        meta = VectorStore.parse_metadata(fname)
        assert meta["dosya_adi"] == fname
