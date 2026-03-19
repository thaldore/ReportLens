"""
ReportLens MSSQL Vektör Veritabanı Yönetim Modülü.
SQL Server 2022+ vektör fonksiyonlarını kullanarak semantik arama ve metadata filtreleme sağlar.
"""
import hashlib
import json
import uuid
import pyodbc
from pathlib import Path
import struct
import time
from typing import Dict, List, Optional, Tuple, Any

from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.config import Config
from core.logging_config import get_logger

logger = get_logger(__name__)


class VectorStore:
    """MSSQL tabanlı vektör veritabanı yönetimi."""

    def __init__(self):
        self.embeddings = OllamaEmbeddings(
            model=Config.EMBEDDING_MODEL,
            base_url=Config.OLLAMA_BASE_URL,
        )
        self.conn_str = (
            f"DRIVER={Config.MSSQL_DRIVER};"
            f"SERVER={Config.MSSQL_HOST};"
            f"DATABASE={Config.MSSQL_DB};"
            f"UID={Config.MSSQL_USER};"
            f"PWD={Config.MSSQL_PASS};"
            "TrustServerCertificate=yes;"
        )
        self.table_name = Config.MSSQL_TABLE
        self._ensure_table()
        # Bellek içi vektör önbelleği (Fallback performansı için)
        self._vector_cache = None # List[Dict] -> [{id: ..., vector: ...}]
        self._cache_timestamp = 0

    def _get_connection(self):
        return pyodbc.connect(self.conn_str)

    def _ensure_table(self):
        """Veritabanı ve vektör tablosunun var olduğundan emin olur, yoksa oluşturur."""
        # 1. Önce master veritabanına bağlanıp DB kontrolü yapalım
        master_conn_str = (
            f"DRIVER={Config.MSSQL_DRIVER};"
            f"SERVER={Config.MSSQL_HOST};"
            f"DATABASE=master;"
            f"UID={Config.MSSQL_USER};"
            f"PWD={Config.MSSQL_PASS};"
            "TrustServerCertificate=yes;"
        )
        try:
            with pyodbc.connect(master_conn_str, autocommit=True) as conn:
                cursor = conn.cursor()
                cursor.execute(f"IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '{Config.MSSQL_DB}') CREATE DATABASE [{Config.MSSQL_DB}]")
        except Exception as e:
            logger.error(f"Veritabanı oluşturma hatası: {e}")

        # 2. Tabloyu oluştur
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
                            Payload NVARCHAR(MAX), -- JSON tipi için SQL Server sürümüne göre NVARCHAR(MAX) daha güvenli
                            CreatedAt DATETIME DEFAULT GETDATE()
                        );
                        CREATE INDEX IX_{self.table_name}_Metadata ON {self.table_name} (Birim, Yil, FileName);
                    END
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Tablo oluşturma hatası: {e}")


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
        if len(parts) >= 1: metadata["birim"] = parts[0]
        if len(parts) >= 2: metadata["yil"] = parts[1]
        if len(parts) >= 3: metadata["tur"] = "_".join(parts[2:])
        return metadata

    # ── İndeksleme ────────────────────────────────────────────────────

    def index_documents(self, force_reindex: bool = False) -> int:
        md_files = list(Config.PROCESSED_DATA_DIR.glob("**/*.md"))
        if not md_files:
            logger.error("İndekslenecek dosya bulunamadı!")
            return 0

        # Eğer veritabanı tamamen boşsa force_reindex'i True yapalım
        if not force_reindex:
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                    if cursor.fetchone()[0] == 0:
                        logger.info("  ℹ️ Veritabanı boş tespit edildi, tam indeksleme başlatılıyor...")
                        force_reindex = True
            except Exception:
                pass

        indexed_hashes = {} if force_reindex else self._get_indexed_hashes()
        files_to_index = []


        for md_file in md_files:
            file_hash = self._compute_file_hash(md_file)
            if force_reindex or md_file.name not in indexed_hashes or indexed_hashes[md_file.name] != file_hash:
                files_to_index.append(md_file)
                indexed_hashes[md_file.name] = file_hash

        if not files_to_index:
            logger.info("Tüm dosyalar zaten indekslenmiş.")
            return 0

        fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE, chunk_overlap=Config.CHUNK_OVERLAP
        )

        total_chunks = 0
        for md_file in files_to_index:
            try:
                content = md_file.read_text(encoding="utf-8")
                semantic_chunks = self._semantic_split(content, fallback_splitter)
                meta = self.parse_metadata(md_file.name)

                # Eski verileri temizle
                self._delete_file_chunks(md_file.name)

                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    for chunk_text, bolum in semantic_chunks:
                        if len(chunk_text.strip()) < Config.MIN_CHUNK_CONTENT_LENGTH:
                            continue
                        
                        vector = self.embeddings.embed_query(chunk_text)
                        # Vektörü binary formatta sakla (veya SQL Vector tipine uygun çeviri)
                        import struct
                        vector_blob = struct.pack(f'{len(vector)}f', *vector)
                        
                        payload = json.dumps({
                            "bolum_basligi": bolum,
                            "content": chunk_text,
                            **meta
                        }, ensure_ascii=False)

                        cursor.execute(f"""
                            INSERT INTO {self.table_name} (FileName, Birim, Yil, Tur, BolumBasligi, Content, Vector, Payload)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (md_file.name, meta.get('birim'), meta.get('yil'), meta.get('tur'), bolum, chunk_text, vector_blob, payload))
                    
                    conn.commit()
                total_chunks += len(semantic_chunks)
                logger.info(f" ✅ {md_file.name} başarıyla indekslendi.")

            except Exception as e:
                logger.error(f" ❌ {md_file.name} hatası: {e}")

        self._save_indexed_hashes(indexed_hashes)
        self._vector_cache = None # Önbelleği temizle
        return total_chunks

    def _delete_file_chunks(self, filename: str):
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"DELETE FROM {self.table_name} WHERE FileName = ?", (filename,))
                conn.commit()
        except Exception:
            pass

    # ── Semantik Chunking (Aynen Korundu) ─────────────────────────────
    # (Metodlar: _semantic_split, _protect_tables, _split_preserving_tables vb.)
    # Kısıtlı alan nedeniyle burada özetlenmiştir, orijinal mantık korunmalıdır.

    def _semantic_split(self, content: str, fallback_splitter) -> list:
        # Orijinal semantic split mantığınızı buraya dahil ediyorum.
        import re as _re
        content = self._protect_tables(content)
        heading_pattern = _re.compile(r'^(#{1,3})\s+(.+)$', _re.MULTILINE)
        sections = []
        last_end, current_heading = 0, "Genel"
        for match in heading_pattern.finditer(content):
            section_text = content[last_end:match.start()].strip()
            if section_text: sections.append((section_text, current_heading))
            current_heading = match.group(2).strip()
            last_end = match.start()
        remaining = content[last_end:].strip()
        if remaining: sections.append((remaining, current_heading))
        
        result = []
        for section_text, heading in (sections or [(content.strip(), "Genel")]):
            if len(section_text) > Config.CHUNK_SIZE * 2:
                sub_chunks = self._split_preserving_tables(section_text, fallback_splitter)
                for sub in sub_chunks: result.append((sub, heading))
            else: result.append((section_text, heading))
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
        if current_block: blocks.append(('table' if in_table else 'text', '\n'.join(current_block)))
        result = []
        for b_type, b_text in blocks:
            if b_type == 'table' or len(b_text) <= Config.CHUNK_SIZE * 2: result.append(b_text)
            else: result.extend(fallback_splitter.split_text(b_text))
        return result

    # ── Arama ─────────────────────────────────────────────────────────

    def search(self, query: str, k: int = None, birim: str = None, yil: str = None, filename: str = None) -> str:
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
        
        # 1. Aşama: SQL üzerinden adayları çek
        # (Eğer VECTOR_DISTANCE destekleniyorsa doğrudan SQL'de yap, yoksa tüm adayları çek)
        sql_native = f"""
            SELECT TOP ({k}) Content, FileName, Birim, Yil, 
            VECTOR_DISTANCE('cosine', CAST(? AS VARBINARY(MAX)), Vector) as distance
            FROM {self.table_name}
            {where_sql}
            ORDER BY distance ASC
        """
        
        import struct
        query_blob = struct.pack(f'{len(query_vector)}f', *query_vector)
        
        try:
            # Önce native SQL denemesi
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql_native, [query_blob] + params)
                results = cursor.fetchall()
            
            context_parts = []
            for row in results:
                content, source, b, y, dist = row
                context_parts.append(f"[Kaynak: {source} | Birim: {b} | Yıl: {y}]\n{content}")
            return "\n\n---\n\n".join(context_parts) if context_parts else "İlgili veri bulunamadı."

        except Exception as e:
            # 2. Aşama: Fallback - Python tarafında benzerlik hesaplama
            if "[42000]" in str(e) or "VECTOR_DISTANCE" in str(e):
                logger.info("  ⚠️ SQL VECTOR_DISTANCE hatası, optimize edilmiş Python-side ranking'e geçiliyor...")
                # --- AKILLI ÖNBELLEKLEME VE HIBRID ARAMA (MS-V2) ---
                try:
                    # 1. Önbelleği kontrol et veya yükle (Tüm tabloyu bir kez RAM'e alır)
                    if self._vector_cache is None:
                        logger.info("  📥 Vektör tablosu RAM'e yükleniyor (hızlı fallback için)...")
                        with self._get_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute(f"SELECT Id, Vector, Birim, Yil, FileName FROM [{self.table_name}]")
                            self._vector_cache = cursor.fetchall()
                            self._cache_timestamp = time.time()
                    
                    # 2. RAM üzerinde filtrele (Birim, Yıl, Dosya)
                    import numpy as np
                    q_vec = np.array(query_vector)
                    candidates = []
                    
                    # Vektörleri unpack et ve benzerlik hesapla
                    for row_id, v_blob, b_name, y_name, f_name in self._vector_cache:
                        # Filtreleri uygula
                        if filename and f_name != filename: continue
                        if birim and b_name != birim: continue
                        if yil and y_name != yil: continue
                        
                        v_len = len(v_blob) // 4
                        v = np.array(struct.unpack(f'{v_len}f', v_blob))
                        sim = np.dot(q_vec, v) / (np.linalg.norm(q_vec) * np.linalg.norm(v))
                        candidates.append((sim, row_id))
                    
                    if not candidates:
                        return "İlgili veri bulunamadı."
                    
                    # 3. Sırala ve Top-K ID'leri belirle
                    candidates.sort(key=lambda x: x[0], reverse=True)
                    top_k_ids = [c[1] for c in candidates[:k]]
                    top_k_scores = {c[1]: c[0] for c in candidates[:k]}
                    
                    # 4. Sadece en alakalı metinleri DB'den çek (IO tasarrufu)
                    id_placeholders = ",".join(["?"] * len(top_k_ids))
                    sql_details = f"SELECT Content, FileName, Birim, Yil, Id FROM [{self.table_name}] WHERE Id IN ({id_placeholders})"
                    
                    with self._get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute(sql_details, top_k_ids)
                        detail_rows = cursor.fetchall()
                    
                    detail_map = {row[4]: row for row in detail_rows}
                    context_parts = []
                    for rid in top_k_ids:
                        if rid in detail_map:
                            content, src, b, y, _ = detail_map[rid]
                            context_parts.append(f"[Kaynak: {src} | Birim: {b} | Yıl: {y} | Skor: {top_k_scores[rid]:.3f}]\n{content}")
                    
                    return "\n\n---\n\n".join(context_parts)
                
                except Exception as fe:
                    logger.error(f"Fallback arama hatası: {fe}")
                    return f"Arama hatası: {str(fe)[:100]}"
            
            logger.error(f"Genel arama hatası: {e}")
            return f"Analiz sırasında bir sorun oluştu: {str(e)[:100]}"


    def get_collection_info(self) -> Dict:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                count = cursor.fetchone()[0]
                return {"toplam_nokta": count, "durum": "aktif (MSSQL-V2)"}
        except Exception:
            return {"toplam_nokta": 0, "durum": "bağlantı hatası"}

    def get_file_content(self, filename: str, limit: int = None) -> List[Dict]:
        """Belirli bir dosyanın tüm parçalarını veya limit kadarını getirir."""
        limit_sql = f"TOP ({limit})" if limit else ""
        sql = f"""
            SELECT {limit_sql} Content, BolumBasligi, Payload
            FROM [{self.table_name}]
            WHERE FileName = ?
            ORDER BY Id -- Veya varsa chunk_index
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


