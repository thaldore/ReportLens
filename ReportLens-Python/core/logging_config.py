"""
ReportLens Merkezi Loglama Yapılandırması.
Tüm modüller bu modülden logger alır. Tekrarlayan basicConfig çağrıları ortadan kalkar.
"""
import logging
import sys

_configured = False


def setup_logging(level=logging.INFO):
    """Merkezi loglama yapılandırmasını kurar. Sadece bir kez çalışır."""
    global _configured
    if _configured:
        return

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    # Mevcut handler'ları temizle
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Modül için yapılandırılmış logger döner."""
    setup_logging()
    return logging.getLogger(name)
