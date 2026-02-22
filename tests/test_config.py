"""
Config modülü testleri.
"""
import os
from pathlib import Path

import pytest

from core.config import Config


class TestConfig:
    """Config sınıfı testleri."""

    def test_default_values(self):
        assert Config.MODEL_ID == os.getenv("MODEL_ID", "llama3.1:8b")
        assert Config.EMBEDDING_MODEL == os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        assert Config.CHUNK_SIZE == int(os.getenv("CHUNK_SIZE", "1000"))
        assert Config.SEARCH_K == int(os.getenv("SEARCH_K", "8"))

    def test_directories_are_paths(self):
        assert isinstance(Config.RAW_DATA_DIR, Path)
        assert isinstance(Config.PROCESSED_DATA_DIR, Path)
        assert isinstance(Config.VECTOR_DB_DIR, Path)

    def test_base_dir_structure(self):
        assert Config.RAW_DATA_DIR.name == "raw_data"
        assert Config.PROCESSED_DATA_DIR.name == "processed"
        assert Config.VECTOR_DB_DIR.name == "vector_db"

    def test_ensure_directories(self):
        Config.ensure_directories()
        assert Config.RAW_DATA_DIR.exists()
        assert Config.PROCESSED_DATA_DIR.exists()
        assert Config.VECTOR_DB_DIR.exists()
        assert Config.IMAGES_DIR.exists()
