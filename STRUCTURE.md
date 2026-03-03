# ReportLens Proje Mimarisi ve Klasör Yapısı

Bu rapor, projenin sürdürülebilirliği, geliştirilebilirliği ve veri gizliliği standartlarını korumak amacıyla oluşturulmuş klasör hiyerarşisini açıklar.

## 1. Klasör Hiyerarşisi

```text
ReportLens/
├── core/                               # Uygulamanın beyni (AI ve Veri İşleme)
│   ├── __init__.py                     # Paket tanımı
│   ├── config.py                       # Merkezi yapılandırma (model, chunk, sıcaklık, re-ranker, prompt cache)
│   ├── logging_config.py               # Merkezi loglama
│   ├── brain.py                        # Çok Ajanlı orkestrasyon merkezi (prompt caching + birim doğrulama)
│   ├── processor.py                    # PDF/DOCX/Excel/CSV → Markdown dönüştürücü (OCR destekli)
│   ├── vector_store.py                 # Qdrant vektör veritabanı (semantik chunking + tablo koruma + metadata)
│   ├── output_validator.py             # LLM çıktı doğrulama (halüsinasyon, format, tekrar, JSON, birim adı)
│   ├── reranker.py                     # Cross-encoder re-ranking (CPU tabanlı, lazy-loaded)
│   └── agents/                         # Uzman ajanlar
│       ├── __init__.py
│       ├── analyzer.py                 # Kalite Analiz Uzmanı (RAG + birim kısaltma tablosu)
│       ├── report_writer.py            # Rapor Yazım Uzmanı (YÖKAK 7-bölüm yapısal rapor)
│       ├── consistency_checker.py      # Tutarsızlık Analiz Uzmanı (beyan doğrulama + confidence)
│       ├── rubric_evaluator.py         # Rubrik Değerlendirme Uzmanı (1-5 puanlama)
│       ├── rubric_validator.py         # Rubrik Denetçi Uzmanı (blind review)
│       └── mock_generator.py           # Hibrit Sahte Veri Üretici (BOLUM 1: anket + BOLUM 2: metin)
├── ui/                                 # Kullanıcı arayüzü
│   └── main.py                         # Streamlit arayüzü (9 sekmeli portal + test sonuçları)
├── Data/                               # Veri merkezi (Gizlilik öncelikli — .gitignore kapsamında)
│   ├── raw_data/                       # Ham raporlar (PDF, DOCX, Excel, CSV)
│   ├── processed/                      # Markdown dosyaları (işlenmiş çıktılar)
│   │   └── images/                     # DOCX'lerden çıkarılan görseller
│   ├── vector_db/                      # Qdrant yerel depolama
│   │   ├── indexed_hashes.json         # Artımlı indeksleme hash takibi
│   │   └── meta.json                   # Koleksiyon metadata
│   └── test_results/                   # Kapsamlı test sonuçları (JSON)
├── models/                             # Yerel model yapılandırmaları
│   └── reporter_expert.Modelfile       # Ollama uzman ajan rolü (legacy)
├── scripts/                            # Yardımcı scriptler
│   ├── check_db.py                     # Vektör veritabanı durum kontrolü
│   ├── debug_agno.py                   # Agno framework hata ayıklama
│   ├── full_system_test.py             # Kapsamlı sistem testi (51+ test, JSON çıktı)
│   └── docker_entrypoint.sh            # Docker başlatma scripti
├── tests/                              # Test altyapısı (pytest)
│   ├── __init__.py
│   ├── test_config.py                  # Config testleri
│   ├── test_processor.py              # DOCX/metadata parse testleri
│   ├── test_vector_store.py           # Vektör arama ve metadata testleri
│   └── test_output_validator.py       # Çıktı doğrulama testleri
├── .dockerignore                       # Docker build dışı dosyalar
├── .gitignore                          # Git takip dışı dosyalar
├── Dockerfile                          # Konteynerizasyon
├── docker-compose.yml                  # Servis orkestrasyonu (Ollama + Qdrant + App)
├── requirements.txt                    # Python bağımlılıkları (+ sentence-transformers)
├── EXPECTED_OUTPUTS.md                 # Modül çıktı spesifikasyonları (kalite referansı)
├── SETUP.md                            # Kurulum rehberi (Docker + venv)
├── STRUCTURE.md                        # Bu dosya
└── README.md                           # Proje tanıtımı
```

## 2. Mimari Yaklaşımlar

### Çok Ajanlı Orkestrasyon (Multi-Agent Orchestration)
`brain.py` Python kodu ile deterministik orkestrasyon yapar (LLM tabanlı orchestrator yerine). Her modül için gerekli ajanları çağırır, RAG araması yapar ve sonuçları birleştirir.
- **Prompt Caching:** Ollama `keep_alive` parametresi ile model bellekte tutulur (varsayılan: 30 dakika).
- **Multi-step LLM:** Öz değerlendirme raporu üretiminde her kriter ayrı LLM çağrısı ile analiz edilir.

### Birim Ad Doğrulama (Anti-Hallucination)
Tüm çıktılarda birim kısaltma tablosu (IIBF=İktisadi ve İdari Bilimler, ITBF=İnsan ve Toplum Bilimleri vb.) ile halüsinasyon edilmiş birim adları otomatik tespit ve düzeltilir.

### Re-Ranking ile Kaliteli Retrieval
`reranker.py` modülü `cross-encoder/ms-marco-MiniLM-L-6-v2` modelini CPU üzerinde çalıştırarak vektör arama sonuçlarını yeniden sıralar. GPU ile çakışma olmaz, lazy-loaded.

### Değerlendirme ve Denetim (Evaluation & Validation)
Rubrik modülünde **blind review** mekanizması: `Rubric Evaluator` puanlama yaparken, `Rubric Validator` evaluator'ın puanını görmeden bağımsız puanlama yapar.

### Çıktı Doğrulama Katmanı (Output Validation)
`output_validator.py` tüm LLM çıktılarını kullanıcıya göstermeden önce doğrular:
- **Halüsinasyon Dedektörü:** Çıktıdaki sayıları bağlamda arar
- **Format Doğrulama:** Accent-insensitive (Türkçe→ASCII normalize) bölüm başlığı kontrolü
- **Tekrar Dedektörü:** %80+ benzer paragrafları tespit eder
- **JSON Parser:** LLM'den structured JSON çıktı ayrıştırma
- **Birim Doğrulama:** Yanlış birim adlarını otomatik düzeltme

### Semantik Chunking + Tablo Koruma
Markdown başlık tabanlı (`#`, `##`, `###`) chunking ile rapor yapısı korunur. Tablo blokları (`|...|`) chunk sınırlarından bölünmez. OCR'den gelen tekrarlı tablo sütunları temizlenir.

### Hibrit Tutarsızlık Analizi
Kullanıcı beyanlarında metin ve anket ayrı input alanlarında toplanır. Rapor "Mutlak Gerçek" kabul edilir. Her iddia ayrı analiz edilir ve DOĞRU/YANLIŞ/BİLGİ YOK etiketleri güven seviyesiyle verilir.
Mock veri üretiminde fallback mekanizması: BOLUM başlıkları bulunamazsa otomatik yeniden dener.

### Kapsamlı Test Altyapısı
`scripts/full_system_test.py` ile 51+ test senaryosu çalıştırılır. Sonuçlar `Data/test_results/` dizinine JSON olarak kaydedilir ve Streamlit UI'da görüntülenir.

### Veri Gizliliği (Local-First)
Tüm işlem süreci kullanıcının kendi makinesinde gerçekleşir. Ollama ile yerel LLM, Qdrant ile yerel vektör veritabanı kullanılır. 3. parti bulut servislerine veri çıkışı tamamen kapatılmıştır.
