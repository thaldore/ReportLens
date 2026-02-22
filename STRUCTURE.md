# ReportLens Proje Mimarisi ve Klasör Yapısı

Bu rapor, projenin sürdürülebilirliği, geliştirilebilirliği ve veri gizliliği standartlarını korumak amacıyla oluşturulmuş klasör hiyerarşisini açıklar.

## 1. Klasör Hiyerarşisi

```text
ReportLens/
├── core/                           # Uygulamanın beyni (AI ve Veri İşleme)
│   ├── __init__.py                 # Paket tanımı
│   ├── config.py                   # Merkezi yapılandırma (tüm ayarlar tek noktadan)
│   ├── logging_config.py           # Merkezi loglama yapılandırması
│   ├── brain.py                    # Çok Ajanlı orkestrasyon merkezi
│   ├── processor.py                # PDF/DOCX → Markdown dönüştürücü (tablo, görsel, başlık desteği)
│   ├── vector_store.py             # Qdrant vektör veritabanı yönetimi (artımlı indeksleme)
│   └── agents/                     # Uzman ajanlar
│       ├── __init__.py
│       ├── analyzer.py             # Kalite Analiz Uzmanı ajanı
│       ├── report_writer.py        # Rapor Yazım Uzmanı ajanı
│       └── consistency_checker.py  # Tutarsızlık Analiz Uzmanı ajanı
├── ui/                             # Kullanıcı arayüzü
│   └── main.py                     # Streamlit arayüzü (6 sayfa)
├── Data/                           # Veri merkezi (Gizlilik öncelikli)
│   ├── raw_data/                   # Ham raporlar (PDF/DOCX)
│   ├── processed/                  # Markdown dosyaları
│   │   └── images/                 # DOCX'ten çıkarılan görseller
│   └── vector_db/                  # Qdrant yerel depolama (Docker dışı mod)
├── models/                         # Yerel model yapılandırmaları
│   └── reporter_expert.Modelfile   # Ollama uzman ajan rolü
├── scripts/                        # Yardımcı scriptler
│   ├── check_db.py                 # Vektör DB durum kontrolü
│   ├── debug_agno.py               # Agno debug aracı
│   └── docker_entrypoint.sh        # Docker başlatma scripti
├── tests/                          # Test altyapısı
│   ├── __init__.py
│   ├── test_processor.py           # Processor testleri
│   ├── test_vector_store.py        # Vector store testleri
│   └── test_config.py              # Config testleri
├── Dockerfile                      # Konteynerizasyon (healthcheck, entrypoint)
├── docker-compose.yml              # 3 servis: App + Ollama + Qdrant
├── requirements.txt                # Python bağımlılıkları (versiyonlu)
├── SETUP.md                        # Kurulum rehberi
├── STRUCTURE.md                    # Bu dosya
└── README.md                       # Proje tanıtımı
```

## 2. Mimari Yaklaşımlar

### Temiz ve Modüler (Clean Architecture)
Kod ve arayüz tamamen ayrılmıştır. `core/` katmanı hiçbir UI bağımlılığı içermez. Yarın Streamlit yerine React kullanılsa sadece `ui/` değişir.

### Çok Ajanlı Sistem
Tek ajan yerine görev ayrımı yapılmıştır:
- **Analiz Ajanı:** Verileri değerlendirir, PUKÖ döngüsü analizi yapar
- **Rapor Yazım Ajanı:** Analizleri yapılandırılmış rapora dönüştürür
- **Tutarsızlık Ajanı:** Metin/anket ile rapor karşılaştırması yapar

### Merkezi Yapılandırma
Tüm ayarlar `core/config.py`'de toplanmıştır. Ortam değişkenleri ile geçersiz kılınabilir. Kod içinde hardcoded değer yoktur.

### Veri Gizliliği (Zero Data Leak)
`Data/` altındaki hiçbir dosya dışarıya gönderilmez. Ollama yerel çalışır, Qdrant yerel/Docker içinde çalışır. 3. parti API bağımlılığı yoktur.

### Qdrant Vektör Veritabanı
- Artımlı indeksleme (sadece yeni/değişen dosyalar)
- Metadata zenginleştirme (birim, yıl, rapor türü)
- Filtrelemeli arama
- Yerel dosya modu (geliştirme) veya sunucu modu (Docker)

### Genişletilebilirlik
Qdrant, 100 raporluk bir sistemden 100.000+ raporluk bir kurumsal hafızaya ölçeklenebilir altyapıdadır.
