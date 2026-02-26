"""
ReportLens Rapor İşleme Modülü.
PDF, DOCX, Excel ve CSV dosyalarını gelişmiş Markdown formatına dönüştürür.
Tablo, başlık, liste ve görsel desteği içerir.
"""
from pathlib import Path

import pandas as pd
import pymupdf4llm
from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from tqdm import tqdm

from core.config import Config
from core.logging_config import get_logger

logger = get_logger(__name__)


class ReportProcessor:
    def __init__(self):
        self.raw_dir = Config.RAW_DATA_DIR
        self.processed_dir = Config.PROCESSED_DATA_DIR
        Config.ensure_directories()

    # ── PDF İşleme ────────────────────────────────────────────────────

    def process_pdf(self, file_path: Path, output_path: Path):
        """PDF dosyasını Markdown'a çevirir. Görsel tabanlı PDF'ler için otomatik OCR kullanır."""
        md_text = ""
        try:
            md_text = pymupdf4llm.to_markdown(str(file_path))
        except Exception as e:
            logger.warning(f"pymupdf4llm hatası ({file_path.name}): {e}")

        # Çıktı çok kısaysa (taranmış/görsel tabanlı PDF) OCR ile yeniden dene
        if len(md_text.strip()) < 200:
            logger.info(f"  🔍 OCR modu deneniyor: {file_path.name} (metin uzunluğu: {len(md_text.strip())})")
            ocr_text = self._pdf_ocr_fallback(file_path)
            if len(ocr_text.strip()) > len(md_text.strip()):
                md_text = ocr_text
                logger.info(f"  ✅ OCR başarılı: {file_path.name} ({len(md_text)} karakter)")
            else:
                logger.warning(f"  ⚠️ OCR çıktısı da yetersiz: {file_path.name}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_text)

    def _pdf_ocr_fallback(self, file_path: Path) -> str:
        """Görsel tabanlı PDF sayfaları için PyMuPDF + Tesseract OCR kullanarak metin çıkarır."""
        try:
            import fitz  # PyMuPDF (pymupdf4llm ile birlikte gelir)
            doc = fitz.open(str(file_path))
            md_parts = []

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Önce normal metin çıkarmayı dene
                text = page.get_text("text").strip()

                if len(text) < 50:
                    # Görüntü tabanlı sayfa — Tesseract OCR uygula
                    try:
                        tp = page.get_textpage_ocr(flags=0, full=True, language="tur+eng")
                        text = page.get_text(textpage=tp).strip()
                    except Exception as ocr_err:
                        logger.warning(f"OCR hatası (sayfa {page_num + 1}): {ocr_err}")

                if text:
                    md_parts.append(f"## Sayfa {page_num + 1}\n\n{text}")

            doc.close()
            return "\n\n---\n\n".join(md_parts) if md_parts else ""

        except Exception as e:
            logger.error(f"OCR fallback genel hata ({file_path.name}): {e}")
            return ""

    def check_empty_processed_files(self) -> list:
        """Boş veya çok kısa olan işlenmiş dosyaları tespit eder (yeniden işleme için)."""
        empty_files = []
        if not self.processed_dir.exists():
            return empty_files
        for md_file in self.processed_dir.glob("*.md"):
            if md_file.stat().st_size < 200:  # 200 byte'tan küçük = boş/içeriksiz
                raw_candidates = list(self.raw_dir.glob(f"{md_file.stem}.*"))
                raw_candidates = [f for f in raw_candidates if f.suffix.lower() in [".pdf", ".docx", ".xlsx", ".csv"]]
                empty_files.append({
                    "md_file": md_file,
                    "raw_file": raw_candidates[0] if raw_candidates else None,
                    "size": md_file.stat().st_size,
                })
        return empty_files

    def reprocess_empty_files(self) -> int:
        """Boş işlenmiş dosyaları zorla yeniden işler. İşlenen dosya sayısını döner."""
        empty = self.check_empty_processed_files()
        if not empty:
            logger.info("Yeniden işlenecek boş dosya yok.")
            return 0

        count = 0
        for item in empty:
            if item["raw_file"] is None:
                logger.warning(f"Ham dosya bulunamadı: {item['md_file'].name}")
                continue
            try:
                logger.info(f"  🔄 Yeniden işleniyor: {item['raw_file'].name}")
                suffix = item["raw_file"].suffix.lower()
                if suffix == ".pdf":
                    self.process_pdf(item["raw_file"], item["md_file"])
                elif suffix == ".docx":
                    self.process_docx(item["raw_file"], item["md_file"])
                elif suffix in [".xlsx", ".xls"]:
                    self.process_excel(item["raw_file"], item["md_file"])
                elif suffix == ".csv":
                    self.process_csv(item["raw_file"], item["md_file"])
                count += 1
                logger.info(f"  ✅ {item['raw_file'].name} tamamlandı ({item['md_file'].stat().st_size} byte)")
            except Exception as e:
                logger.error(f"Yeniden işleme hatası ({item['raw_file'].name}): {e}")
        return count

    # ── DOCX İşleme (Gelişmiş) ───────────────────────────────────────

    def process_docx(self, file_path: Path, output_path: Path):
        """DOCX dosyasını gelişmiş Markdown'a çevirir.
        Tablo, başlık, liste ve görsel desteği içerir.
        """
        doc = Document(str(file_path))
        md_content = []

        # Görselleri çıkar
        image_map = self._extract_docx_images(doc, file_path.stem)

        # Gövde elemanlarını sırasıyla işle (paragraf ve tablo sırası korunur)
        for child in doc.element.body.iterchildren():
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            if tag == "p":
                para = Paragraph(child, doc)
                line = self._process_paragraph(para, image_map)
                if line is not None:
                    md_content.append(line)

            elif tag == "tbl":
                table = Table(child, doc)
                md_table = self._table_to_markdown(table)
                if md_table:
                    md_content.append(f"\n{md_table}\n")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(md_content))

    def _process_paragraph(self, para: Paragraph, image_map: dict):
        """Paragrafı Markdown'a dönüştürür (başlık, liste, görsel algılama)."""
        parts = []

        # Görselleri kontrol et
        img_paths = self._get_paragraph_images(para, image_map)
        for img_path in img_paths:
            parts.append(f"![Görsel]({img_path})")

        text = para.text.strip()
        style_name = para.style.name if para.style else ""

        if not text and not img_paths:
            return None

        if text:
            if style_name.startswith("Heading"):
                level = self._get_heading_level(style_name)
                parts.insert(0, f"{'#' * level} {text}")
            elif "List" in style_name or "Madde" in style_name:
                parts.insert(0, f"- {text}")
            else:
                parts.insert(0, text)

        return "\n".join(parts) if parts else None

    @staticmethod
    def _get_heading_level(style_name: str) -> int:
        """Heading stilinden seviye çıkarır (1-6)."""
        for char in style_name:
            if char.isdigit():
                return min(int(char), 6)
        return 1

    @staticmethod
    def _table_to_markdown(table: Table) -> str:
        """DOCX tablosunu Markdown tablo formatına çevirir."""
        if not table.rows:
            return ""

        rows = []
        for row in table.rows:
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            rows.append("| " + " | ".join(cells) + " |")

        if len(rows) >= 1:
            num_cols = len(table.rows[0].cells)
            separator = "| " + " | ".join(["---"] * num_cols) + " |"
            rows.insert(1, separator)

        return "\n".join(rows)

    # ── Görsel Çıkarma ────────────────────────────────────────────────

    def _extract_docx_images(self, doc: Document, file_stem: str) -> dict:
        """DOCX'ten tüm görselleri çıkarır ve kaydeder."""
        images_dir = Config.IMAGES_DIR / file_stem
        images_dir.mkdir(parents=True, exist_ok=True)
        image_map = {}

        for rel_id, rel in doc.part.rels.items():
            if "image" in rel.reltype:
                try:
                    image_data = rel.target_part.blob
                    image_ext = rel.target_ref.split(".")[-1]
                    image_name = f"{rel_id}.{image_ext}"
                    image_path = images_dir / image_name

                    with open(image_path, "wb") as f:
                        f.write(image_data)

                    image_map[rel_id] = str(image_path)
                except Exception as e:
                    logger.warning(f"Görsel çıkarılamadı ({rel_id}): {e}")

        if image_map:
            logger.info(f"  🖼️ {file_stem}: {len(image_map)} görsel çıkarıldı")
        return image_map

    @staticmethod
    def _get_paragraph_images(para: Paragraph, image_map: dict) -> list:
        """Paragraftaki görsel referanslarını bulur."""
        image_paths = []
        blips = para._element.findall(f".//{qn('a:blip')}")
        for blip in blips:
            rid = blip.get(qn("r:embed"))
            if rid and rid in image_map:
                image_paths.append(image_map[rid])
        return image_paths

    # ── Excel İşleme ──────────────────────────────────────────────────

    def process_excel(self, file_path: Path, output_path: Path):
        """Excel dosyasını (xlsx/xls) Markdown'a çevirir.
        Her sayfa ayrı bir bölüm olarak işlenir. Tüm tablolar Markdown formatına dönüştürülür.
        """
        md_content = []
        md_content.append(f"# {file_path.stem}\n")

        try:
            # Tüm sayfaları oku
            excel_data = pd.read_excel(str(file_path), sheet_name=None, dtype=str)

            for sheet_name, df in excel_data.items():
                md_content.append(f"## Sayfa: {sheet_name}\n")

                if df.empty:
                    md_content.append("*Bu sayfa boş.*\n")
                    continue

                # NaN değerleri boş stringe çevir
                df = df.fillna("")

                # DataFrame'i Markdown tablosuna çevir
                md_table = self._dataframe_to_markdown(df)
                md_content.append(md_table)

                # Satır ve sütun bilgisi
                md_content.append(f"\n*({df.shape[0]} satır, {df.shape[1]} sütun)*\n")

            logger.info(f"  📊 {file_path.name}: {len(excel_data)} sayfa işlendi")

        except Exception as e:
            logger.error(f"Excel işleme hatası ({file_path.name}): {e}")
            md_content.append(f"*Excel dosyası işlenirken hata oluştu: {e}*\n")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))

    # ── CSV İşleme ────────────────────────────────────────────────────

    def process_csv(self, file_path: Path, output_path: Path):
        """CSV dosyasını Markdown'a çevirir."""
        md_content = []
        md_content.append(f"# {file_path.stem}\n")

        try:
            # Farklı encoding'leri dene
            df = None
            for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1254"]:
                try:
                    df = pd.read_csv(str(file_path), encoding=encoding, dtype=str)
                    break
                except UnicodeDecodeError:
                    continue

            if df is None:
                raise ValueError("Dosya encoding'i belirlenemedi")

            # NaN değerleri boş stringe çevir
            df = df.fillna("")

            # DataFrame'i Markdown tablosuna çevir
            md_table = self._dataframe_to_markdown(df)
            md_content.append(md_table)

            md_content.append(f"\n*({df.shape[0]} satır, {df.shape[1]} sütun)*\n")
            logger.info(f"  📋 {file_path.name}: {df.shape[0]} satır işlendi")

        except Exception as e:
            logger.error(f"CSV işleme hatası ({file_path.name}): {e}")
            md_content.append(f"*CSV dosyası işlenirken hata oluştu: {e}*\n")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))

    # ── Ortak Yardımcı ────────────────────────────────────────────────

    @staticmethod
    def _dataframe_to_markdown(df: pd.DataFrame) -> str:
        """Pandas DataFrame'i Markdown tablo formatına çevirir."""
        if df.empty:
            return "*Veri yok.*"

        # Sütun başlıkları
        headers = [str(col).strip().replace("\n", " ") for col in df.columns]
        header_line = "| " + " | ".join(headers) + " |"
        separator = "| " + " | ".join(["---"] * len(headers)) + " |"

        # Veri satırları
        rows = []
        for _, row in df.iterrows():
            cells = [str(val).strip().replace("\n", " ").replace("|", "\\|") for val in row]
            rows.append("| " + " | ".join(cells) + " |")

        return "\n".join([header_line, separator] + rows)

    # ── Toplu Dönüştürme ──────────────────────────────────────────────

    def convert_files(self) -> int:
        """Tüm ham dosyaları Markdown formatına çevirir.
        Desteklenen formatlar: PDF, DOCX, XLSX, XLS, CSV
        Alt dizinleri de tarar (recursive). Zaten işlenmiş dosyaları atlar.
        Returns: İşlenen dosya sayısı.
        """
        supported_extensions = ["*.pdf", "*.docx", "*.xlsx", "*.xls", "*.csv"]
        files = []
        for ext in supported_extensions:
            files.extend(self.raw_dir.glob(f"**/{ext}"))

        if not files:
            logger.warning("İşlenecek dosya bulunamadı!")
            return 0

        logger.info(f"{len(files)} adet dosya bulundu...")
        processed_count = 0

        for file_path in tqdm(files, desc="Dönüştürülüyor"):
            try:
                output_path = self.processed_dir / f"{file_path.stem}.md"

                # Zaten yeterli içerikle işlenmişse atla (boş dosyaları yeniden işle)
                if output_path.exists() and output_path.stat().st_size > 500:
                    continue

                suffix = file_path.suffix.lower()
                if suffix == ".pdf":
                    self.process_pdf(file_path, output_path)
                elif suffix == ".docx":
                    self.process_docx(file_path, output_path)
                elif suffix in [".xlsx", ".xls"]:
                    self.process_excel(file_path, output_path)
                elif suffix == ".csv":
                    self.process_csv(file_path, output_path)

                processed_count += 1

            except Exception as e:
                logger.error(f"Hata: {file_path.name} - {str(e)}")

        logger.info(f"Dönüşüm tamamlandı. {processed_count} dosya işlendi.")
        return processed_count


if __name__ == "__main__":
    processor = ReportProcessor()
    processor.convert_files()
