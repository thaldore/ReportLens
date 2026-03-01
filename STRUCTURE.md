# ReportLens Proje Mimarisi ve Klasör Yapısı

Bu rapor, projenin sürdürülebilirliği, geliştirilebilirliği ve veri gizliliği standartlarını korumak amacıyla oluşturulmuş klasör hiyerarşisini açıklar.

## 1. Klasör Hiyerarşisi

```text
ReportLens/
├── core/                               # Uygulamanın beyni (AI ve Veri İşleme)
│   ├── __init__.py                     # Paket tanımı
│   ├── config.py                       # Merkezi yapılandırma (model, chunk, sıcaklık)
│   ├── logging_config.py               # Merkezi loglama
│   ├── brain.py                        # Çok Ajanlı orkestrasyon merkezi
│   ├── processor.py                    # PDF/DOCX/Excel/CSV → Markdown dönüştürücü (OCR destekli)
│   ├── vector_store.py                 # Qdrant vektör veritabanı (semantik chunking + metadata)
│   ├── output_validator.py             # LLM çıktı doğrulama (halüsinasyon, format, tekrar)
│   └── agents/                         # Uzman ajanlar
│       ├── __init__.py
│       ├── analyzer.py                 # Kalite Analiz Uzmanı (RAG tabanlı soru-cevap)
│       ├── report_writer.py            # Rapor Yazım Uzmanı (YÖKAK yapısal rapor)
│       ├── consistency_checker.py      # Tutarsızlık Analiz Uzmanı (beyan doğrulama)
│       ├── rubric_evaluator.py         # Rubrik Değerlendirme Uzmanı (1-5 puanlama)
│       ├── rubric_validator.py         # Rubrik Denetçi Uzmanı (blind review)
│       └── mock_generator.py           # Hibrit Sahte Veri Üretici (anket + metin)
├── ui/                                 # Kullanıcı arayüzü
│   └── main.py                         # Streamlit arayüzü (8 sekmeli portal)
├── Data/                               # Veri merkezi (Gizlilik öncelikli — .gitignore kapsamında)
│   ├── raw_data/                       # Ham raporlar (PDF, DOCX, Excel, CSV)
│   ├── processed/                      # Markdown dosyaları (işlenmiş çıktılar)
│   │   └── images/                     # DOCX'lerden çıkarılan görseller
│   └── vector_db/                      # Qdrant yerel depolama
│       ├── indexed_hashes.json         # Artımlı indeksleme hash takibi
│       └── meta.json                   # Koleksiyon metadata
├── models/                             # Yerel model yapılandırmaları
│   └── reporter_expert.Modelfile       # Ollama uzman ajan rolü (legacy)
├── scripts/                            # Yardımcı scriptler
│   ├── check_db.py                     # Vektör veritabanı durum kontrolü
│   ├── debug_agno.py                   # Agno framework hata ayıklama
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
├── requirements.txt                    # Python bağımlılıkları
├── EXPECTED_OUTPUTS.md                 # Modül çıktı spesifikasyonları (kalite referansı)
├── SETUP.md                            # Kurulum rehberi
├── STRUCTURE.md                        # Bu dosya
└── README.md                           # Proje tanıtımı
```

## 2. Mimari Yaklaşımlar

### Çok Ajanlı Orkestrasyon (Multi-Agent Orchestration)
`brain.py` Python kodu ile deterministik orkestrasyon yapar (LLM tabanlı orchestrator yerine). Her modül için gerekli ajanları çağırır, RAG araması yapar ve sonuçları birleştirir.

### Değerlendirme ve Denetim (Evaluation & Validation)
Rubrik modülünde **blind review** mekanizması: `Rubric Evaluator` puanlama yaparken, `Rubric Validator` evaluator'ın puanını görmeden bağımsız puanlama yapar. İki puan karşılaştırılarak tutarsızlıklar tespit edilir.

### Çıktı Doğrulama Katmanı (Output Validation)
`output_validator.py` tüm LLM çıktılarını kullanıcıya göstermeden önce doğrular:
- **Halüsinasyon Dedektörü:** Çıktıdaki sayıları bağlamda arar
- **Format Doğrulama:** Beklenen bölüm başlıklarını kontrol eder
- **Tekrar Dedektörü:** %80+ benzer paragrafları tespit eder

### Semantik Chunking
Markdown başlık tabanlı (`#`, `##`, `###`) chunking ile rapor yapısı korunur. Her chunk'a `bolum_basligi` metadata'sı eklenerek hassas filtreleme yapılır.

### Hibrit Tutarsızlık Analizi
Kullanıcı beyanlarında metin ve anket ayrı input alanlarında toplanır. Rapor "Mutlak Gerçek" (Ground Truth) kabul edilir. Her iddia ayrı ayrı analiz edilir ve DOĞRU/YANLIŞ/BİLGİ YOK etiketleri güven seviyesiyle (HIGH/MEDIUM/LOW) birlikte verilir.

### Veri Gizliliği (Local-First)
Tüm işlem süreci kullanıcının kendi makinesinde gerçekleşir. Ollama ile yerel LLM, Qdrant ile yerel vektör veritabanı kullanılır. 3. parti bulut servislerine veri çıkışı tamamen kapatılmıştır.
