"""
ReportLens MSSQL Vektör Veritabanı Yönetim Modülü.
SQL Server 2025 native VECTOR tipi ve VECTOR_DISTANCE fonksiyonu ile
semantik arama ve metadata filtreleme sağlar.
"""
import hashlib
import json
import logging
import os
import re
import struct
import pyodbc
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.config import Config
from core.logging_config import get_logger

logger = get_logger(__name__)

# nomic-embed-text vektör boyutu
VECTOR_DIMENSION = 768


class VectorStore:
    """SQL Server 2025 native VECTOR tipi ile vektör veritabanı yönetimi."""

    def __init__(self):
        self.embeddings = OllamaEmbeddings(
            model=Config.EMBEDDING_MODEL,
            base_url=Config.OLLAMA_BASE_URL,
        )
        # Bağlantı dizesini oluştur (Windows Auth desteği ile)
        if Config.MSSQL_USER and Config.MSSQL_PASS:
            self.conn_str = (
                f"DRIVER={Config.MSSQL_DRIVER};"
                f"SERVER={Config.MSSQL_HOST};"
                f"DATABASE={Config.MSSQL_DB};"
                f"UID={Config.MSSQL_USER};"
                f"PWD={Config.MSSQL_PASS};"
                "TrustServerCertificate=yes;"
            )
        else:
            self.conn_str = (
                f"DRIVER={Config.MSSQL_DRIVER};"
                f"SERVER={Config.MSSQL_HOST};"
                f"DATABASE={Config.MSSQL_DB};"
                "Trusted_Connection=yes;"
                "TrustServerCertificate=yes;"
            )

        self.table_name = Config.MSSQL_TABLE
        self._ensure_table()

    def _get_connection(self):
        return pyodbc.connect(self.conn_str)

    def _ensure_table(self):
        """Veritabanı ve vektör tablosunun var olduğundan emin olur, yoksa oluşturur."""
        # 1. Önce master veritabanına bağlanıp DB kontrolü yapalım
        if Config.MSSQL_USER and Config.MSSQL_PASS:
            master_conn_str = (
                f"DRIVER={Config.MSSQL_DRIVER};"
                f"SERVER={Config.MSSQL_HOST};"
                f"DATABASE=master;"
                f"UID={Config.MSSQL_USER};"
                f"PWD={Config.MSSQL_PASS};"
                "TrustServerCertificate=yes;"
            )
        else:
            master_conn_str = (
                f"DRIVER={Config.MSSQL_DRIVER};"
                f"SERVER={Config.MSSQL_HOST};"
                f"DATABASE=master;"
                "Trusted_Connection=yes;"
                "TrustServerCertificate=yes;"
            )
        try:
            with pyodbc.connect(master_conn_str, autocommit=True) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '{Config.MSSQL_DB}') "
                    f"CREATE DATABASE [{Config.MSSQL_DB}]"
                )
        except Exception as e:
            logger.error(f"Veritabanı oluşturma hatası: {e}")

        # 2. Tabloyu oluştur — SQL Server 2025 native VECTOR tipi
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '{self.table_name}')
                    BEGIN
                        CREATE TABLE {self.table_name} (
                            Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
                            FileName NVARCHAR(255),
                            Birim NVARCHAR(100),
                            Yil NVARCHAR(10),
                            Tur NVARCHAR(255),
                            BolumBasligi NVARCHAR(MAX),
                            Content NVARCHAR(MAX),
                            Vector VECTOR({VECTOR_DIMENSION}) NOT NULL,
                            Payload NVARCHAR(MAX),
                            CreatedAt DATETIME DEFAULT GETDATE()
                        );
                        CREATE INDEX IX_{self.table_name}_Metadata 
                            ON {self.table_name} (Birim, Yil, FileName);
                    END
                """)
                conn.commit()
                logger.info(f"Tablo hazır: {self.table_name} (VECTOR({VECTOR_DIMENSION}))")
        except Exception as e:
            # Eğer VECTOR tipi desteklenmiyorsa VARBINARY(MAX) fallback
            if "VECTOR" in str(e).upper() or "15600" in str(e):
                logger.warning(
                    f"SQL Server VECTOR tipi desteklenmiyor, VARBINARY(MAX) kullanılıyor. "
                    f"SQL Server 2025 gereklidir. Hata: {e}"
                )
                self._ensure_table_legacy()
            else:
                logger.error(f"Tablo oluşturma hatası: {e}")

    def _ensure_table_legacy(self):
        """SQL Server 2022 uyumlu tablo (VARBINARY fallback)."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = '{self.table_name}')
                    BEGIN
                        CREATE TABLE {self.table_name} (
                            Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
                            FileName NVARCHAR(255),
                            Birim NVARCHAR(100),
                            Yil NVARCHAR(10),
                            Tur NVARCHAR(255),
                            BolumBasligi NVARCHAR(MAX),
                            Content NVARCHAR(MAX),
                            Vector VARBINARY(MAX),
                            Payload NVARCHAR(MAX),
                            CreatedAt DATETIME DEFAULT GETDATE()
                        );
                        CREATE INDEX IX_{self.table_name}_Metadata 
                            ON {self.table_name} (Birim, Yil, FileName);
                    END
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Legacy tablo oluşturma hatası: {e}")

    # ── Dosya Hash Yönetimi ──────────────────────────────────────────

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
        parts = filename.replace(".md", "").split("_")
        metadata = {"dosya_adi": filename}
        if len(parts) >= 1:
            metadata["birim"] = parts[0]
        if len(parts) >= 2:
            metadata["yil"] = parts[1]
        if len(parts) >= 3:
            metadata["tur"] = "_".join(parts[2:])
        return metadata

    # ── Vektör Dönüşüm Yardımcıları ──────────────────────────────────

    @staticmethod
    def _vector_to_json(vector: List[float]) -> str:
        """Vektörü yuvarlayarak ve boşlukları atarak NVARCHAR(8000) altına indirir."""
        # 6 basamak yuvarlama + kompak JSON (Boşluksuz)
        # Bu yöntem SQL Server'daki 'ntext to vector' hatasını (Error 22018) çözer.
        rounded = [round(float(x), 6) for x in vector]
        return json.dumps(rounded, separators=(',', ':'))

    @staticmethod
    def _vector_to_binary(vector: List[float]) -> bytes:
        """Vektörü binary formata çevirir (legacy VARBINARY desteği)."""
        return struct.pack(f'{len(vector)}f', *vector)

    def _detect_vector_column_type(self) -> str:
        """Tablodaki Vector kolonunun tipini tespit eder."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = '{self.table_name}' AND COLUMN_NAME = 'Vector'
                """)
                row = cursor.fetchone()
                if row:
                    return row[0].upper()
        except Exception:
            pass
        return "UNKNOWN"

    # ── İndeksleme ────────────────────────────────────────────────────

    def index_documents(self, force_reindex: bool = False) -> int:
        md_files = list(Config.PROCESSED_DATA_DIR.glob("**/*.md"))
        if not md_files:
            logger.error(" ❌ İndekslenecek dosya bulunamadı! Data/processed klasörünü kontrol edin.")
            return 0

        # Eğer veritabanı tamamen boşsa force_reindex'i True yapalım
        db_empty = False
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                row = cursor.fetchone()
                if row and row[0] == 0:
                    db_empty = True
                    logger.info("  ℹ️ Veritabanı boş tespit edildi, tam indeksleme başlatılıyor...")
                    force_reindex = True
        except Exception as e:
            logger.warning(f"  ⚠️ Veritabanı doluluk kontrolü yapılamadı: {e}")

        indexed_hashes = {} if force_reindex else self._get_indexed_hashes()
        files_to_index = []

        for md_file in md_files:
            file_hash = self._compute_file_hash(md_file)
            if force_reindex or md_file.name not in indexed_hashes or indexed_hashes[md_file.name] != file_hash:
                files_to_index.append(md_file)
                indexed_hashes[md_file.name] = file_hash

        if not files_to_index:
            logger.info("  ✅ Tüm dosyalar zaten güncel ve indekslenmiş.")
            return 0

        # Kolon tipini tespit et
        col_type = self._detect_vector_column_type()
        use_native_vector = col_type in ("VECTOR", "UNKNOWN")
        logger.info(f"  🚀 İndeksleme başlıyor... Kolon tipi: {col_type}, Native VECTOR: {use_native_vector}")

        fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE, chunk_overlap=Config.CHUNK_OVERLAP
        )

        total_chunks = 0
        error_count = 0
        
        # Parallel embedding using ThreadPoolExecutor
        max_workers = 10 
        
        for md_file in files_to_index:
            try:
                content = md_file.read_text(encoding="utf-8")
                semantic_chunks = self._semantic_split(content, fallback_splitter)
                meta = self.parse_metadata(md_file.name)

                # ℹ️ IMPORTANT: Always clear OLD data for a file to prevent duplicates
                self._delete_file_chunks(md_file.name)

                # Collect chunks for parallel embedding
                valid_chunks = []
                for chunk_text, bolum in semantic_chunks:
                    if len(chunk_text.strip()) >= Config.MIN_CHUNK_CONTENT_LENGTH:
                        valid_chunks.append((chunk_text, bolum))
                
                if not valid_chunks:
                    continue

                def _embed_task(item):
                    txt, blm = item
                    try:
                        vec = self.embeddings.embed_query(txt)
                        return (vec, txt, blm)
                    except Exception as ve:
                        logger.error(f"  ❌ Embedding error ({md_file.name}): {ve}")
                        return (None, txt, blm)

                logger.info(f"  ⏳ Vectorizing {len(valid_chunks)} chunks for {md_file.name}...")
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    results = list(executor.map(_embed_task, valid_chunks))

                # Batch write successful results
                batch_data = [r for r in results if r[0] is not None]
                
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    chunk_count = 0
                    for vector, chunk_text, bolum in batch_data:
                        if len(vector) != VECTOR_DIMENSION:
                            continue

                        payload = json.dumps({
                            "bolum_basligi": bolum,
                            "content": chunk_text,
                            **meta
                        }, ensure_ascii=False)

                        try:
                            if use_native_vector:
                                vector_value = self._vector_to_json(vector)
                                cursor.execute(f"""
                                    INSERT INTO {self.table_name} 
                                    (FileName, Birim, Yil, Tur, BolumBasligi, Content, Vector, Payload)
                                    VALUES (?, ?, ?, ?, ?, ?, CAST('{vector_value}' AS VECTOR({VECTOR_DIMENSION})), ?)
                                """, (
                                    md_file.name, meta.get('birim'), meta.get('yil'),
                                    meta.get('tur'), bolum, chunk_text, payload
                                ))
                            else:
                                vector_blob = self._vector_to_binary(vector)
                                cursor.execute(f"""
                                    INSERT INTO {self.table_name} 
                                    (FileName, Birim, Yil, Tur, BolumBasligi, Content, Vector, Payload)
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    md_file.name, meta.get('birim'), meta.get('yil'),
                                    meta.get('tur'), bolum, chunk_text, vector_blob, payload
                                ))
                            chunk_count += 1
                        except Exception as ie:
                            logger.error(f"  ❌ Chunk save error ({md_file.name}): {ie}")
                            error_count += 1

                    conn.commit()
                total_chunks += chunk_count
                logger.info(f"  ✅ {md_file.name} successfully processed ({chunk_count} chunks).")

            except Exception as e:
                logger.error(f"  ❌ Error processing {md_file.name}: {str(e)}")
                error_count += 1

        self._save_indexed_hashes(indexed_hashes)
        logger.info(f"  📊 Indexing result: {total_chunks} chunks successfully written. {error_count} errors.")
        return total_chunks

    def _delete_file_chunks(self, filename: str):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {self.table_name} WHERE FileName = ?", (filename,))
                conn.commit()
        except Exception:
            pass

    # ── Semantik Chunking ─────────────────────────────────────────────

    def _semantic_split(self, content: str, fallback_splitter) -> list:
        content = self._protect_tables(content)
        heading_pattern = re.compile(r'^(#{1,3})\s+(.+)$', re.MULTILINE)
        sections = []
        last_end, current_heading = 0, "Genel"
        for match in heading_pattern.finditer(content):
            section_text = content[last_end:match.start()].strip()
            if section_text:
                sections.append((section_text, current_heading))
            current_heading = match.group(2).strip()
            last_end = match.start()
        remaining = content[last_end:].strip()
        if remaining:
            sections.append((remaining, current_heading))

        result = []
        for section_text, heading in (sections or [(content.strip(), "Genel")]):
            if len(section_text) > Config.CHUNK_SIZE * 2:
                sub_chunks = self._split_preserving_tables(section_text, fallback_splitter)
                for sub in sub_chunks:
                    result.append((sub, heading))
            else:
                result.append((section_text, heading))
        return result

    @staticmethod
    def _protect_tables(content: str) -> str:
        lines = content.split('\n')
        cleaned = []
        for line in lines:
            if '|' in line and line.count('|') > 6:
                cells = [c.strip() for c in line.split('|') if c.strip()]
                unique_cells, seen = [], set()
                for cell in cells:
                    if cell not in seen:
                        unique_cells.append(cell)
                        seen.add(cell)
                line = '| ' + ' | '.join(unique_cells) + ' |'
            cleaned.append(line)
        return '\n'.join(cleaned)

    def _split_preserving_tables(self, text: str, fallback_splitter) -> list:
        blocks, current_block, in_table = [], [], False
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
        result = []
        for b_type, b_text in blocks:
            if b_type == 'table' or len(b_text) <= Config.CHUNK_SIZE * 2:
                result.append(b_text)
            else:
                result.extend(fallback_splitter.split_text(b_text))
        return result

    # ── Arama — SQL Server 2025 Native VECTOR_DISTANCE ────────────────

    def search(self, query: str, k: int = None, birim: str = None,
               yil: str = None, filename: str = None) -> str:
        k = k or Config.SEARCH_K
        query_vector = self.embeddings.embed_query(query)

        where_clauses = []
        params = []

        if filename:
            where_clauses.append("FileName = ?")
            params.append(filename)
        else:
            if birim:
                where_clauses.append("Birim = ?")
                params.append(birim)
            if yil:
                where_clauses.append("Yil = ?")
                params.append(yil)

        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        # SQL Server 2025 native VECTOR_DISTANCE
        # KESIN ÇÖZÜM: Vektörü SQL string literal olarak gömüyoruz.
        query_vector_json = self._vector_to_json(query_vector)

        sql_native = f"""
            SELECT TOP ({k}) Content, FileName, Birim, Yil,
            VECTOR_DISTANCE('cosine', CAST('{query_vector_json}' AS VECTOR({VECTOR_DIMENSION})), Vector) AS distance
            FROM {self.table_name}
            {where_sql}
            ORDER BY distance ASC
        """

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql_native, params)
                results = cursor.fetchall()

            context_parts = []
            for row in results:
                content, source, b, y, dist = row
                score = 1.0 - float(dist) if dist is not None else 0.0
                context_parts.append(
                    f"[Kaynak: {source} | Birim: {b} | Yıl: {y} | Skor: {score:.3f}]\n{content}"
                )
            return "\n\n---\n\n".join(context_parts) if context_parts else "İlgili veri bulunamadı."

        except Exception as e:
            # Fallback: VARBINARY formatı ile Python taraflı cosine similarity
            if "VECTOR_DISTANCE" in str(e) or "VECTOR" in str(e) or "[42000]" in str(e):
                logger.warning(f"Native VECTOR_DISTANCE desteklenmiyor, Python fallback kullanılıyor: {e}")
                return self._search_fallback(query_vector, k, where_clauses, params)

            logger.error(f"Genel arama hatası: {e}")
            return f"Analiz sırasında bir sorun oluştu: {str(e)[:100]}"

    def _search_fallback(self, query_vector: List[float], k: int,
                         where_clauses: List[str], params: List) -> str:
        """VARBINARY fallback — Python taraflı cosine similarity hesaplama."""
        try:
            import numpy as np

            where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT Id, Content, FileName, Birim, Yil, Vector "
                    f"FROM [{self.table_name}] {where_sql}",
                    params
                )
                rows = cursor.fetchall()

            if not rows:
                return "İlgili veri bulunamadı."

            # Vektörleri decode et ve cosine similarity hesapla
            q_vec = np.array(query_vector, dtype=np.float32)
            q_norm = np.linalg.norm(q_vec)
            if q_norm > 0:
                q_vec = q_vec / q_norm

            scored_results = []
            for row in rows:
                rid, content, fname, birim, yil, v_blob = row
                if v_blob is None:
                    continue
                v_len = len(v_blob) // 4
                v = np.array(struct.unpack(f'{v_len}f', v_blob), dtype=np.float32)
                v_norm = np.linalg.norm(v)
                if v_norm > 0:
                    v = v / v_norm
                similarity = float(np.dot(q_vec, v))
                scored_results.append((content, fname, birim, yil, similarity))

            # En yüksek skorlu sonuçları sırala
            scored_results.sort(key=lambda x: x[4], reverse=True)
            top_results = scored_results[:k]

            context_parts = []
            for content, source, b, y, score in top_results:
                context_parts.append(
                    f"[Kaynak: {source} | Birim: {b} | Yıl: {y} | Skor: {score:.3f}]\n{content}"
                )
            return "\n\n---\n\n".join(context_parts) if context_parts else "İlgili veri bulunamadı."

        except Exception as fe:
            logger.error(f"Fallback arama hatası: {fe}")
            return f"Arama hatası: {str(fe)[:100]}"

    def get_collection_info(self) -> Dict:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                count = cursor.fetchone()[0]

                # Kolon tipini kontrol et
                col_type = self._detect_vector_column_type()
                engine = "SQL Server 2025 (Native VECTOR)" if col_type == "VECTOR" else "SQL Server (VARBINARY Fallback)"

                return {"toplam_nokta": count, "durum": f"aktif ({engine})"}
        except Exception:
            return {"toplam_nokta": 0, "durum": "bağlantı hatası"}

    def get_file_content(self, filename: str, limit: int = None) -> List[Dict]:
        """Belirli bir dosyanın tüm parçalarını veya limit kadarını getirir."""
        limit_sql = f"TOP ({limit})" if limit else ""
        sql = f"""
            SELECT {limit_sql} Content, BolumBasligi, Payload
            FROM [{self.table_name}]
            WHERE FileName = ?
            ORDER BY Id
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (filename,))
                rows = cursor.fetchall()

                results = []
                for row in rows:
                    content, bolum, payload_raw = row
                    payload = json.loads(payload_raw) if payload_raw else {}
                    results.append({
                        "content": content,
                        "bolum": bolum,
                        "payload": payload
                    })
                return results
        except Exception as e:
            logger.error(f"Dosya içeriği getirme hatası ({filename}): {e}")
            return []
