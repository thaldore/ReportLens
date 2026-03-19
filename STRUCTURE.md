# ReportLens Proje Mimarisi (Hybrid Ecosystem)

Bu döküman, projenin Python ve .NET ekosistemlerinin nasıl bir arada çalıştığını ve ortak mimari prensiplerini açıklar.

## 1. Genel Dizin Hiyerarşisi

```text
ReportLens/
├── ReportLens-Python/              # Mevcut Python Ajan Sistemi
│   ├── core/                       # Analiz, Yazım, Denetim Ajanları
│   ├── ui/                         # Streamlit Arayüzü
│   ├── Data/                       # Yerel Veri (Processed, Raw, Vector_DB)
│   ├── scripts/                    # Test ve Yardımcı Scriptler
│   └── Dockerfile                  # Python Container Tanımı
├── ReportLens-Microsoft-Agent-Framework/ # Yeni .NET Ajan Sistemi
│   ├── frontend/                   # .NET Web UI
│   ├── backend/                    # .NET Modular Monolith Backend
│   └── ReportLens-LLM/             # AI Mikroservisi (C#)
├── docker-compose.yml              # TÜM sistemi orkestre eden ana yapı
├── README.md                       # Genel Tanıtım
└── STRUCTURE.md                    # Bu dosya
```

## 2. Ortak Teknoloji Yığıtı (Shared Stack)

Her iki sistem de aşağıdaki altyapıyı ortak kullanır:

- **LLM Engine**: [Ollama](https://ollama.ai/) (Yerel modeller: llama3.1, gemma2 vb.)
- **Vector/Relational DB**: **Microsoft SQL Server 2022+** (Vektör arama yetenekleri ile)
- **Containerization**: Docker & Docker Compose

## 3. Mimari Yaklaşımlar

### Veri Gizliliği (Zero-Leakage)
Tüm boru hattı (data pipeline) yerel makinede veya güvenli yerel sunucuda çalışır. 3. taraf AI servislerine (OpenAI, Anthropic vb.) veri gönderilmez.

### Multi-Agent Orchestration
Her iki platformda da ajanlar belirli görevlerde (Analiz, Yazım, Denetim) uzmanlaşmıştır. Python tarafı Agno/LangChain kullanırken, .NET tarafı Microsoft Semantic Kernel kullanır.

### Modular Monolith & Clean Architecture
Sürdürülebilirlik için .NET tarafında Clean Architecture prensipleri uygulanır. Python tarafında ise "Central Brain" paternine sadık kalınır.

---
© 2026 ReportLens Architecture Guide
