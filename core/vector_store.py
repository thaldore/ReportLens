"""
ReportLens Qdrant Vektör Veritabanı Yönetim Modülü.
Artımlı indeksleme, metadata zenginleştirme ve filtrelemeli arama destekler.
"""
import hashlib
import json
import uuid
from pathlib import Path
from typing import Dict, Optional

from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
    VectorParams,
)

from core.config import Config
from core.logging_config import get_logger

logger = get_logger(__name__)


class VectorStore:
    """Qdrant tabanlı vektör veritabanı yönetimi."""

    def __init__(self):
        self.embeddings = OllamaEmbeddings(
            model=Config.EMBEDDING_MODEL,
            base_url=Config.OLLAMA_BASE_URL,
        )

        # Qdrant bağlantısı: sunucu veya yerel dosya modu
        if Config.QDRANT_URL:
            self.client = QdrantClient(url=Config.QDRANT_URL)
            logger.info(f"Qdrant sunucusuna bağlanıldı: {Config.QDRANT_URL}")
        else:
            Config.VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
            self.client = QdrantClient(path=str(Config.VECTOR_DB_DIR))
            logger.info(f"Yerel Qdrant depolama: {Config.VECTOR_DB_DIR}")

        self.collection_name = Config.QDRANT_COLLECTION
        self._ensure_collection()

    def _ensure_collection(self):
        """Koleksiyonun var olduğundan emin olur, yoksa oluşturur."""
        try:
            # Doğrudan kontrol (exists check yerine get_collection daha güvenilirdir)
            self.client.get_collection(self.collection_name)
            return
        except Exception:
            logger.info(f"Koleksiyon bulunamadı, oluşturuluyor: {self.collection_name}")
            
            # Vektör boyutunu tespit et (EMBEDDING_MODEL'e göre)
            test_embedding = self.embeddings.embed_query("test")
            vector_size = len(test_embedding)

            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size, distance=Distance.COSINE
                ),
            )
            logger.info(
                f"Koleksiyon oluşturuldu: {self.collection_name} (dim={vector_size})"
            )

    # ── Dosya Hash Yönetimi (Artımlı İndeksleme) ──────────────────────

    @staticmethod
    def _compute_file_hash(file_path: Path) -> str:
        return hashlib.md5(file_path.read_bytes()).hexdigest()

    def _get_indexed_hashes(self) -> Dict[str, str]:
        hash_file = Config.VECTOR_DB_DIR / "indexed_hashes.json"
        if hash_file.exists():
            return json.loads(hash_file.read_text(encoding="utf-8"))
        return {}

    def _save_indexed_hashes(self, hashes: Dict[str, str]):
        hash_file = Config.VECTOR_DB_DIR / "indexed_hashes.json"
        hash_file.write_text(
            json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ── Metadata Çıkarma ──────────────────────────────────────────────

    @staticmethod
    def parse_metadata(filename: str) -> Dict:
        """Dosya adından metadata çıkarır.
        Örn: Fen_2024_Oz_Degerlendirme_Raporu.md → birim=Fen, yil=2024, tur=Oz_Degerlendirme_Raporu
        """
        parts = filename.replace(".md", "").split("_")
        metadata = {"dosya_adi": filename}

        if len(parts) >= 1:
            metadata["birim"] = parts[0]
        if len(parts) >= 2:
            metadata["yil"] = parts[1]
        if len(parts) >= 3:
            metadata["tur"] = "_".join(parts[2:])

        return metadata

    # ── İndeksleme ────────────────────────────────────────────────────

    def index_documents(self, force_reindex: bool = False) -> int:
        """Markdown dosyalarını indeksler. Artımlı indeksleme destekler.
        Returns: İndekslenen toplam chunk sayısı.
        """
        # Koleksiyonun varlığından emin ol (özellikle force_reprocess sonrası için kritik)
        self._ensure_collection()
        
        md_files = list(Config.PROCESSED_DATA_DIR.glob("**/*.md"))

        if not md_files:
            logger.error("İndekslenecek dosya bulunamadı!")
            return 0

        indexed_hashes = {} if force_reindex else self._get_indexed_hashes()
        files_to_index = []

        for md_file in md_files:
            file_hash = self._compute_file_hash(md_file)
            if (
                md_file.name not in indexed_hashes
                or indexed_hashes[md_file.name] != file_hash
            ):
                files_to_index.append(md_file)
                indexed_hashes[md_file.name] = file_hash

        if not files_to_index:
            logger.info("Tüm dosyalar zaten indekslenmiş.")
            return 0

        logger.info(f"{len(files_to_index)} yeni/güncellenmiş dosya indekslenecek...")

        # Fallback splitter (çok büyük bölümler için)
        fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE, chunk_overlap=Config.CHUNK_OVERLAP
        )

        total_chunks = 0
        for md_file in files_to_index:
            try:
                content = md_file.read_text(encoding="utf-8")

                # Semantik chunking: Markdown başlıklarına göre böl
                semantic_chunks = self._semantic_split(content, fallback_splitter)
                metadata = self.parse_metadata(md_file.name)

                # Eski chunk'ları sil
                self._delete_file_chunks(md_file.name)

                # Vektörleştir ve kaydet
                points = []
                for i, (chunk_text, bolum_basligi) in enumerate(semantic_chunks):
                    # Çok kısa chunk'ları filtrele
                    if len(chunk_text.strip()) < Config.MIN_CHUNK_CONTENT_LENGTH:
                        continue

                    embedding = self.embeddings.embed_query(chunk_text)
                    points.append(
                        PointStruct(
                            id=str(uuid.uuid4()),
                            vector=embedding,
                            payload={
                                **metadata,
                                "chunk_index": i,
                                "content": chunk_text,
                                "bolum_basligi": bolum_basligi,
                            },
                        )
                    )

                if points:
                    batch_size = 100
                    for j in range(0, len(points), batch_size):
                        self.client.upsert(
                            collection_name=self.collection_name,
                            points=points[j : j + batch_size],
                        )

                total_chunks += len(points)
                logger.info(f"  ✅ {md_file.name}: {len(points)} parça")

            except Exception as e:
                logger.error(f"  ❌ {md_file.name}: {str(e)}")

        self._save_indexed_hashes(indexed_hashes)
        logger.info(f"İndeksleme tamamlandı. Toplam {total_chunks} yeni parça.")
        return total_chunks

    def _delete_file_chunks(self, filename: str):
        """Belirli bir dosyaya ait chunk'ları siler."""
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[
                            FieldCondition(
                                key="dosya_adi", match=MatchValue(value=filename)
                            )
                        ]
                    )
                ),
            )
        except Exception:
            pass  # Koleksiyon boş olabilir

    # ── Semantik Chunking ─────────────────────────────────────────────

    @staticmethod
    def _semantic_split(content: str, fallback_splitter) -> list:
        """Markdown başlıklarına göre semantik chunking yapar.

        Her #, ##, ### başlığı bir bölüm sınırı olarak kullanılır.
        Tablo blokları korunur (chunk sınırlarına bölünmez).
        Çok büyük bölümler fallback_splitter ile alt parçalara bölünür.

        Returns:
            list of (chunk_text, bolum_basligi) tuples
        """
        import re as _re

        # Ön işlem: tablo bloklarını koru (bölünmeyi önle)
        content = VectorStore._protect_tables(content)

        # Markdown başlıklarına göre böl
        heading_pattern = _re.compile(r'^(#{1,3})\s+(.+)$', _re.MULTILINE)

        sections = []
        last_end = 0
        current_heading = "Genel"

        for match in heading_pattern.finditer(content):
            section_text = content[last_end:match.start()].strip()
            if section_text:
                sections.append((section_text, current_heading))
            current_heading = match.group(2).strip()
            last_end = match.start()

        remaining = content[last_end:].strip()
        if remaining:
            sections.append((remaining, current_heading))

        if not sections:
            sections = [(content.strip(), "Genel")]

        # Çok büyük bölümleri alt parçalara böl (tablo bloklarını koru)
        result = []
        for section_text, heading in sections:
            if len(section_text) > Config.CHUNK_SIZE * 2:
                sub_chunks = VectorStore._split_preserving_tables(
                    section_text, fallback_splitter
                )
                for sub in sub_chunks:
                    result.append((sub, heading))
            else:
                result.append((section_text, heading))

        return result

    @staticmethod
    def _protect_tables(content: str) -> str:
        """Tekrarlayan tablo sütunlarını temizler (OCR artefaktları).
        Örn: aynı hücre 8 kez tekrarlanıyorsa tek kopya bırak."""
        import re as _re
        lines = content.split('\n')
        cleaned = []
        for line in lines:
            if '|' in line and line.count('|') > 6:
                # Tablo satırı: tekrarlayan hücreleri temizle
                cells = [c.strip() for c in line.split('|')]
                cells = [c for c in cells if c]  # Boşları kaldır
                if cells:
                    unique_cells = []
                    seen = set()
                    for cell in cells:
                        cell_normalized = _re.sub(r'\s+', ' ', cell.strip())
                        if cell_normalized not in seen:
                            unique_cells.append(cell)
                            seen.add(cell_normalized)
                    line = '| ' + ' | '.join(unique_cells) + ' |'
            cleaned.append(line)
        return '\n'.join(cleaned)

    @staticmethod
    def _split_preserving_tables(text: str, fallback_splitter) -> list:
        """Metni bölerken tablo bloklarını korur."""
        import re as _re
        # Tablo bloklarını bul (| ile başlayan ardışık satırlar)
        blocks = []
        current_block = []
        in_table = False

        for line in text.split('\n'):
            is_table_line = line.strip().startswith('|') and '|' in line[1:]
            if is_table_line:
                if not in_table and current_block:
                    blocks.append(('text', '\n'.join(current_block)))
                    current_block = []
                in_table = True
                current_block.append(line)
            else:
                if in_table and current_block:
                    blocks.append(('table', '\n'.join(current_block)))
                    current_block = []
                in_table = False
                current_block.append(line)

        if current_block:
            blocks.append(('table' if in_table else 'text', '\n'.join(current_block)))

        # Metin bloklarını böl, tablo bloklarını koru
        result = []
        for block_type, block_text in blocks:
            if block_type == 'table' or len(block_text) <= Config.CHUNK_SIZE * 2:
                result.append(block_text)
            else:
                result.extend(fallback_splitter.split_text(block_text))

        return result

    # ── Arama ─────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        k: Optional[int] = None,
        birim: Optional[str] = None,
        yil: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> str:
        """Vektör araması yapar. Opsiyonel birim/yıl/dosya adı filtrelemesi destekler."""
        k = k or Config.SEARCH_K
        query_vector = self.embeddings.embed_query(query)

        # Filtre oluştur
        filter_conditions = []
        if filename:
            # Dosya adı filtresi, birim/yıl filtrelerinden önceliklidir
            filter_conditions.append(
                FieldCondition(key="dosya_adi", match=MatchValue(value=filename))
            )
        else:
            if birim:
                filter_conditions.append(
                    FieldCondition(key="birim", match=MatchValue(value=birim))
                )
            if yil:
                filter_conditions.append(
                    FieldCondition(key="yil", match=MatchValue(value=yil))
                )

        search_filter = Filter(must=filter_conditions) if filter_conditions else None

        # Arama gerçekleştir
        try:
            # En güvenli metod erişimi
            search_func = getattr(self.client, 'search', None)
            
            if search_func:
                search_results = search_func(
                    collection_name=self.collection_name,
                    query_vector=query_vector,
                    query_filter=search_filter,
                    limit=k,
                    with_payload=True,
                )
            else:
                # Fallback: query_points (Modern v1.10+)
                query_points_func = getattr(self.client, 'query_points', None)
                if query_points_func:
                    response = query_points_func(
                        collection_name=self.collection_name,
                        query=query_vector,
                        query_filter=search_filter,
                        limit=k,
                        with_payload=True,
                    )
                    search_results = response.points if hasattr(response, 'points') else []
                else:
                    # Kritik Fallback: Scroll (Vektörsüz arama)
                    search_results = self.client.scroll(
                        collection_name=self.collection_name,
                        scroll_filter=search_filter,
                        limit=k,
                        with_payload=True
                    )[0]
            
            # Sonuçları işle
            context_parts = []
            for point in search_results:
                # Hem PointStruct hem de dict formatını destekle
                payload = getattr(point, 'payload', point) if not isinstance(point, dict) else point.get('payload', {})
                if not isinstance(payload, dict): 
                   payload = {} # Güvenlik

                content = payload.get("content", "")
                if content:
                    source = payload.get("dosya_adi", "bilinmiyor")
                    birim_info = payload.get("birim", "Belirtilmemiş")
                    yil_info = payload.get("yil", "Belirtilmemiş")
                    context_parts.append(
                        f"[Kaynak: {source} | Birim: {birim_info} | Yıl: {yil_info}]\n{content}"
                    )
            
            context = "\n\n---\n\n".join(context_parts)
            if not context:
                return "Bu arama kriterlerine uygun veri bulunamadı."
                
            logger.info(f"Arama: '{query[:50]}...' - {len(search_results)} parça bulundu.")
            return context

        except Exception as e:
            logger.error(f"Kritik Arama Hatası: {str(e)}")
            return f"Analiz için veri çekilirken bir sorun oluştu. (Sistem Notu: {str(e)[:100]})"

    # ── Bilgi ─────────────────────────────────────────────────────────

    def get_collection_info(self) -> Dict:
        """Koleksiyon hakkında bilgi döner."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "toplam_nokta": info.points_count,
                "vektör_boyutu": info.config.params.vectors.size,
                "durum": str(info.status),
            }
        except Exception:
            return {"toplam_nokta": 0, "durum": "koleksiyon bulunamadı"}
