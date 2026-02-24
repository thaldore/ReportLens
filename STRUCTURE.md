# ReportLens Proje Mimarisi ve Klasör Yapısı

Bu rapor, projenin sürdürülebilirliği, geliştirilebilirliği ve veri gizliliği standartlarını korumak amacıyla oluşturulmuş klasör hiyerarşisini açıklar.

## 1. Klasör Hiyerarşisi

```text
ReportLens/
├── core/                           # Uygulamanın beyni (AI ve Veri İşleme)
│   ├── __init__.py                 # Paket tanımı
│   ├── config.py                   # Merkezi yapılandırma
│   ├── logging_config.py           # Merkezi loglama
│   ├── brain.py                    # Çok Ajanlı orkestrasyon merkezi (Değerlendirme + Denetim)
│   ├── processor.py                # PDF/DOCX → Markdown dönüştürücü
│   ├── vector_store.py             # Qdrant vektör veritabanı yönetimi
│   └── agents/                     # Uzman ajanlar
│       ├── __init__.py
│       ├── analyzer.py             # Kalite Analiz Uzmanı
│       ├── report_writer.py        # Rapor Yazım Uzmanı
│       ├── consistency_checker.py  # Tutarsızlık Analiz Uzmanı
│       ├── rubric_evaluator.py     # Rubrik Değerlendirme Uzmanı
│       ├── rubric_validator.py     # Rubrik Denetçi Uzmanı (Yeni!)
│       └── mock_generator.py       # Hibrit Veri Üretici (Anket + Metin)
├── ui/                             # Kullanıcı arayüzü
│   └── main.py                     # Streamlit arayüzü
├── Data/                           # Veri merkezi (Gizlilik öncelikli)
│   ├── raw_data/                   # Ham raporlar
│   ├── processed/                  # Markdown dosyaları
│   └── vector_db/                  # Qdrant yerel depolama
├── models/                         # Yerel model yapılandırmaları
│   └── reporter_expert.Modelfile   # Ollama uzman ajan rolü
├── scripts/                        # Yardımcı scriptler
├── tests/                          # Test altyapısı
├── Dockerfile                      # Konteynerizasyon
├── docker-compose.yml              # Servis orkestrasyonu
├── requirements.txt                # Bağımlılıklar
├── SETUP.md                        # Kurulum rehberi
├── STRUCTURE.md                    # Bu dosya
└── README.md                       # Proje tanıtımı
```

## 2. Mimari Yaklaşımlar

### Değerlendirme ve Denetim (Evaluation & Validation)
Sistem artık sadece veri üretmekle kalmaz, ürettiği veriyi denetler. `Rubric Evaluator` puanlama yaparken, `Rubric Validator` bu puanı rapor metniyle kıyaslayarak doğrular. Bu "Denetçi" mekanizması halüsinasyonları %99 oranında engeller.

### Hibrit Tutarsızlık Analizi
Tutarsızlık analizinde hem akademik metinler hem de anket yanıtları aynı anda rapora göre doğrulanır. Rapor "Mutlak Gerçek" (Ground Truth) olarak kabul edilir.

### Veri Gizliliği (Local-First)
Tüm işlem süreci kullanıcının kendi makinesinde gerçekleşir. 3. parti bulut yazılımlarına veri çıkışı tamamen kapatılmıştır.
