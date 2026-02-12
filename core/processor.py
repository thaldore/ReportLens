import os
import logging
from pathlib import Path
import pymupdf4llm
from docx import Document
from tqdm import tqdm

# Log ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReportProcessor:
    def __init__(self, raw_dir: str, processed_dir: str):
        self.raw_dir = Path(raw_dir)
        self.processed_dir = Path(processed_dir)
        
        # Klasörleri oluştur
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def process_pdf(self, file_path: Path, output_path: Path):
        """PDF dosyasını Markdown'a çevirir."""
        md_text = pymupdf4llm.to_markdown(str(file_path))
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_text)

    def process_docx(self, file_path: Path, output_path: Path):
        """DOCX dosyasını basit Markdown'a çevirir."""
        doc = Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n\n".join(full_text))

    def convert_files(self):
        """Tüm ham dosyaları Markdown formatına çevirir."""
        files = list(self.raw_dir.glob("*.pdf")) + list(self.raw_dir.glob("*.docx"))
        
        if not files:
            logger.warning("İşlenecek dosya bulunamadı!")
            return

        logger.info(f"{len(files)} adet dosya işlenecek...")

        for file_path in tqdm(files, desc="Dönüştürülüyor"):
            try:
                output_path = self.processed_dir / f"{file_path.stem}.md"
                
                # Eğer dosya zaten işlenmişse ve boş değilse atla
                if output_path.exists() and output_path.stat().st_size > 0:
                    continue

                if file_path.suffix.lower() == ".pdf":
                    self.process_pdf(file_path, output_path)
                elif file_path.suffix.lower() == ".docx":
                    self.process_docx(file_path, output_path)

            except Exception as e:
                logger.error(f"Hata: {file_path.name} işlenirken bir sorun oluştu: {str(e)}")

if __name__ == "__main__":
    RAW_DATA = "Data/raw_data"
    PROCESSED_DATA = "Data/processed"
    
    processor = ReportProcessor(RAW_DATA, PROCESSED_DATA)
    processor.convert_files()
    logger.info("Dönüşüm tamamlandı.")
