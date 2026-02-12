# ReportLens Proje Mimarisi ve Klasör Yapısı

Bu rapor, projenin sürdürülebilirliği, geliştirilebilirliği ve veri gizliliği standartlarını korumak amacıyla oluşturulmuş klasör hiyerarşisini açıklar.

## 1. Klasör Hiyerarşisi

```text
ReportLens/
├── core/                   # Uygulamanın beyni (AI ve Veri İşleme)
│   ├── prompts/            # Ajanlar için özel sistem komutları
│   ├── tools/              # Ajanların kullanabileceği özel fonksiyonlar
│   ├── processor.py        # PDF/DOCX -> Markdown dönüştürücü
│   └── brain.py            # Multi-Agent ve LLM yönetim merkezi
├── ui/                     # Kullanıcı arayüzü
│   └── main.py             # Streamlit ana sayfası ve UI bileşenleri
├── Data/                   # Veri merkezi (Gizlilik öncelikli)
│   ├── raw_data/           # Ham raporlar (PDF/DOCX)
│   ├── processed/          # Temizlenmiş ve yapılandırılmış Markdown dosyaları
│   ├── vector_db/          # Hızlı arama için kullanılan vektör veritabanı
│   ├── graph_db/           # İlişkisel analiz için bilgi grafiği veritabanı
│   └── archive/            # Artık kullanılmayan ama saklanan eski veriler
├── models/                 # Yerel model yapılandırmaları
│   └── reporter_expert.Modelfile # Ömür boyu kalıcı uzman ajan rolü
├── scripts/                # Yardımcı scriptler ve bakım araçları
├── Dockerfile              # Konteynerizasyon ayarları
├── docker-compose.yml      # Çoklu konteyner (App + Ollama) yönetimi
├── requirements.txt        # Python kütüphane bağımlılıkları
├── SETUP.md                # Geliştiriciler için kurulum rehberi
└── README.md               # Projenin genel tanıtımı
```

## 2. Mimari Yaklaşımlar

### Temiz ve Modüler (Clean Architecture)
Kod ve arayüz birbirinden tamamen ayrılmıştır. Yarın Streamlit yerine başka bir arayüz (React vb.) kullanmak isterseniz, sadece `ui/` klasörünü değiştirmeniz yeterli olacaktır; `core/` (beyin) kısmına dokunmanıza gerek kalmaz.

### Sürdürülebilirlik ve Geliştirilebilirlik
Tüm veri işleme akışı lineerdir. Yeni bir rapor türü eklendiğindeadece `core/processor.py` güncellenerek sisteme dahil edilebilir.

### Veri Gizliliği (Zero Data Leak)
`Data/` klasörü altındaki hiçbir dosya dışarıdaki bir bulut sistemine gönderilmez. Uygulama tamamen Docker içinde veya yerel sanal ortamda çalışarak tam gizlilik sağlar.

### Genişletilebilirlik
Vektör ve Grafik veritabanları (`Data/vector_db`, `Data/graph_db`) projeyi 100 raporluk bir sistemden 10.000 raporluk bir kurumsal hafızaya taşıyabilecek şekilde ölçeklenebilir altyapıdadır.
