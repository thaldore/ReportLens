# ReportLens Proje Mimarisi (Hybrid Ecosystem)

Bu döküman, projenin Python ve .NET ekosistemlerinin nasıl bir arada çalıştığını ve tüm dosyaların listesini içerir.

## 1. Genel Dizin Hiyerarşisi

```text
ReportLens/
│
│----------------------------------
│Python Agent Framework
│
├── ReportLens-Python/              # AI Ajan Sistemi (Python/Agno)
│   ├── core/                       # Merkezi Beyin ve Ajan Mantığı
│   │   ├── agents/                 # Uzman Ajanlar
│   │   │   ├── __init__.py
│   │   │   ├── analyzer.py         # Kalite Analiz Uzmanı
│   │   │   ├── consistency_checker.py # Tutarsızlık Analizi
│   │   │   ├── mock_generator.py   # Sahte Veri Üretici
│   │   │   ├── report_writer.py    # Rapor Yazıcı
│   │   │   ├── rubric_evaluator.py # Rubrik Notlandırıcı
│   │   │   └── rubric_validator.py # Rubrik Denetleyici
│   │   ├── __init__.py
│   │   ├── brain.py                # QualityBrain (Orkestrasyon)
│   │   ├── config.py               # Konfigürasyon ve VRAM Ayarları
│   │   ├── logging_config.py       # Loglama Yapısı
│   │   ├── output_validator.py     # "Altın Standart" Doğrulayıcı
│   │   ├── processor.py            # OCR ve Chunking İşlemleri
│   │   ├── reranker.py             # Cross-Encoder Reranker
│   │   └── vector_store.py         # MSSQL Vektör Veritabanı
│   ├── Data/                       
│   │   ├── raw_data/               # Ham PDF/MD Dosyaları
│   │   ├── processed/              # İşlenmiş Markdown Verileri
│   │   ├── vector_db/              # İndeksleme Cache
│   │   └── test_results/           # Test Çıktıları
│   ├── scripts/                    
│   │   ├── check_db.py             # DB Durum Kontrolü
│   │   ├── docker_entrypoint.sh    # Docker Başlangıç Scripti
│   │   ├── force_reprocess_all.py  # Yeniden İndeksleme Zorlayıcı
│   │   └── full_system_test.py     # Kapsamlı Sistem Testi
│   ├── tests/                      
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_output_validator.py
│   │   ├── test_processor.py
│   │   └── test_vector_store.py
│   ├── ui/                         
│   │   ├── __init__.py
│   │   └── main.py                 # Streamlit Arayüzü
│   ├── analyzer_main.py            # Bağımsız Analiz Modülü
│   ├── brain_main.py               # Ana Orkestrasyon Giriş Noktası
│   ├── validator_main.py           # Bağımsız Doğrulama Modülü
│   ├── .dockerignore
│   ├── Dockerfile
│   ├── EXPECTED_OUTPUTS.md         # Beklenen Çıktı Örnekleri
│   ├── requirements.txt            # Python Bağımlılıkları
│   └── SETUP.md                    # Kurulum Kılavuzu
│
│----------------------------------
│Microsoft Agent Framework
│
├── ReportLens-Microsoft-Agent-Framework/ # Yeni .NET Ajan Sistemi
│   ├── frontend/                   # .NET Web UI
│   ├── backend/                    # .NET Modular Monolith Backend
│   └── ReportLens-LLM/             # AI Mikroservisi (C#)
├── docker-compose.yml              # Tüm sistemi orkestre eden ana yapı
├── README.md                       # Genel Tanıtım
└── STRUCTURE.md                    # Bu dosya
```

## 2. Ortak Teknoloji Yığıtı (Shared Stack)

- **LLM Engine**: [Ollama](https://ollama.ai/) (llama3.1:latest)
- **Vector/Relational DB**: **Microsoft SQL Server 2022+**
- **Embedding**: `nomic-embed-text`
- **Donanım**: **RTX 4070 (8GB VRAM)** için optimize (**NUM_CTX=8192**)

---
© 2026 ReportLens Architecture Guide
