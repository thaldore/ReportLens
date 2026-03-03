"""
ReportLens Cross-Encoder Re-Ranking Modülü.
Vektör arama sonuçlarını cross-encoder ile yeniden sıralar.
CPU üzerinde çalışır — Ollama GPU kullanımı ile çakışmaz.
"""
import logging
from typing import List, Tuple

from core.config import Config
from core.logging_config import get_logger

logger = get_logger(__name__)

# Lazy loading — model sadece ilk kullanımda yüklenir
_reranker_model = None


def _load_model():
    """Cross-encoder modelini lazy olarak yükler."""
    global _reranker_model
    if _reranker_model is not None:
        return _reranker_model

    try:
        from sentence_transformers import CrossEncoder
        _reranker_model = CrossEncoder(
            Config.RERANKER_MODEL,
            max_length=512,
            device="cpu",  # GPU ile çakışma önleme
        )
        logger.info(f"Re-ranker model yüklendi: {Config.RERANKER_MODEL} (CPU)")
        return _reranker_model
    except ImportError:
        logger.warning(
            "sentence-transformers yüklü değil. Re-ranking devre dışı. "
            "Yüklemek için: pip install sentence-transformers"
        )
        return None
    except Exception as e:
        logger.warning(f"Re-ranker model yüklenemedi: {e}. Re-ranking devre dışı.")
        return None


def rerank(
    query: str,
    documents: List[str],
    top_k: int = None,
    score_threshold: float = 0.01,
) -> List[Tuple[int, str, float]]:
    """Belgeleri sorguya göre cross-encoder ile yeniden sıralar.

    Args:
        query: Arama sorgusu
        documents: Belge metinleri listesi
        top_k: Döndürülecek maksimum belge sayısı (None = hepsi)
        score_threshold: Minimum skor eşiği

    Returns:
        list of (original_index, document_text, score) tuples,
        skorlarına göre azalan sırada
    """
    if not Config.RERANKER_ENABLED:
        # Re-ranking devre dışı — orijinal sırayı koru
        return [(i, doc, 1.0) for i, doc in enumerate(documents)]

    model = _load_model()
    if model is None:
        # Model yüklenemedi — orijinal sırayı koru
        return [(i, doc, 1.0) for i, doc in enumerate(documents)]

    if not documents:
        return []

    try:
        # Cross-encoder puanlama
        pairs = [(query, doc) for doc in documents]
        scores = model.predict(pairs, show_progress_bar=False)

        # İndeksle eşleştir ve sırala
        scored = [
            (i, documents[i], float(scores[i]))
            for i in range(len(documents))
            if float(scores[i]) >= score_threshold
        ]
        scored.sort(key=lambda x: x[2], reverse=True)

        if top_k:
            scored = scored[:top_k]

        logger.info(
            f"Re-ranking: {len(documents)} → {len(scored)} belge "
            f"(top score: {scored[0][2]:.3f} if scored else 'N/A')"
        )
        return scored

    except Exception as e:
        logger.warning(f"Re-ranking hatası: {e}. Orijinal sıra kullanılıyor.")
        return [(i, doc, 1.0) for i, doc in enumerate(documents)]
