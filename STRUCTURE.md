# ReportLens — Proje Yapısı (v2.3)

> Yazılım ve AI Mimari Dokümantasyonu  
> Veri Gizliliği Odaklı Kurumsal Kalite İstihbarat Platformu

---

## 📂 Tam Dosya Hiyerarşisi

```text
ReportLens/
├── ReportLens-Python/                     # 🐍 Python AI Ajan Ekosistemi
│   ├── api/                               # FastAPI REST Sunucusu
│   │   ├── __init__.py
│   │   └── main.py                        # Ana API ve Statik Dosya Sunucu (Port 8000)
│   ├── core/                              # 🧠 Çekirdek İş Mantığı
│   │   ├── agents/                        # AI Ajan Uzmanlıkları
│   │   │   ├── __init__.py
│   │   │   ├── analyzer.py                # Kalite Analiz (English Prompt/Turkish Output)
│   │   │   ├── consistency_checker.py     # Tutarsızlık Denetimi
│   │   │   ├── mock_generator.py          # Sentetik Veri Üretimi
│   │   │   ├── report_writer.py           # YÖKAK Rapor Yazımı
│   │   │   ├── rubric_evaluator.py        # 1-5 Puanlama Ajanı
│   │   │   └── rubric_validator.py        # Bağımsız Denetçi Ajanı
│   │   ├── brain.py                       # QualityBrain (Orkestrasyon)
│   │   ├── config.py                      # Merkezi Konfigürasyon (llama3.1:8b)
│   │   ├── logging_config.py              # Loglama Standartları
│   │   ├── output_validator.py            # Çıktı Kontrolü
│   │   ├── processor.py                   # PDF/DOCX İşleyici
│   │   ├── reranker.py                    # Cross-Encoder Re-ranking
│   │   └── vector_store.py                # SQL Server 2025 Vector Search
│   ├── frontend/                          # 🎨 UI (Python Ortamı)
│   │   ├── css/style.css
│   │   ├── js/app.js
│   │   └── index.html
│   ├── Data/                              # 📊 Ortak Veri Alanı
│   │   ├── raw_data/                      # Ham PDF/DOCX Raporlar
│   │   ├── processed/                     # Markdown Versiyonları
│   │   ├── vector_db/                     # İndeksleme Meta Verileri
│   │   └── test_results/                  # Çıktı Kayıtları
│   ├── scripts/                           # 🛠️ Admin Araçları
│   │   ├── check_db.py
│   │   ├── debug_conn.py
│   │   ├── docker_entrypoint.sh
│   │   ├── force_reprocess_all.py
│   │   └── full_system_test.py
│   ├── tests/                             # 🧪 Test Süreçleri
│   │   ├── __init__.py
│   │   ├── test_config.py
│   │   ├── test_output_validator.py
│   │   ├── test_processor.py
│   │   └── test_vector_store.py
│   ├── _archive/                          # 📦 Eski Kod Arşivi
│   ├── Dockerfile
│   └── requirements.txt
│
├── ReportLens-Microsoft-Agent-Framework/   # 🏢 .NET Enterprise Altyapısı
│   ├── backend/                           # API Gateway & Logic
│   │   ├── src/
│   │   │   ├── Domain/                    # Entities & Value Objects
│   │   │   │   ├── Entities/
│   │   │   │   │   ├── AnalysisResult.cs
│   │   │   │   │   └── Document.cs
│   │   │   ├── Application/               # Use Cases & DTOs
│   │   │   │   ├── DTOs/
│   │   │   │   │   └── AnalysisRequests.cs
│   │   │   │   ├── Interfaces/
│   │   │   │   │   └── IAnalysisService.cs
│   │   │   │   └── Services/
│   │   │   │       └── QualityBrainService.cs (Proxy to LLM-MS)
│   │   │   ├── Infrastructure/            # External Integrations
│   │   │   │   ├── Llm/                   # Ollama Entegrasyonu
│   │   │   │   │   └── OllamaService.cs
│   │   │   │   ├── Processing/            # Markdown Okuyucu
│   │   │   │   │   └── DocumentProcessor.cs
│   │   │   │   └── VectorSearch/          # SQL Vector Searcher
│   │   │   │       └── MssqlVectorSearchService.cs
│   │   │   └── WebApi/                    # API Endpoints
│   │   │       ├── Controllers/
│   │   │       │   └── AnalysisController.cs
│   │   │       ├── Program.cs             # DI & Middleware
│   │   │       ├── appsettings.json
│   │   │       └── ReportLens.WebApi.csproj
│   │   ├── Dockerfile
│   │   └── README.md
│   ├── ReportLens-LLM/                    # 🤖 Agent Engine (Microservice)
│   │   ├── src/
│   │   │   ├── Agents/
│   │   │   │   └── AgentDefinitions.cs    # 6 Ajan (English Prompt/Turkish Output)
│   │   │   ├── Brain/
│   │   │   │   └── QualityBrain.cs        # Merkezi Orkestratör
│   │   │   ├── Controllers/
│   │   │   │   └── LlmController.cs       # Agent Endpoints
│   │   │   ├── VectorSearch/
│   │   │   │   └── VectorStore.cs         # SK Database Provider
│   │   │   ├── Program.cs                 # MS Startup
│   │   │   ├── appsettings.json
│   │   │   └── ReportLens.LLM.csproj
│   │   ├── Dockerfile
│   │   └── README.md
│   ├── frontend/                          # 🎨 UI (MAF Ortamı)
│   │   ├── css/style.css
│   │   ├── js/app.js
│   │   ├── index.html
│   │   ├── nginx.conf
│   │   ├── Dockerfile
│   │   └── README.md
│   └── scripts/
│       └── full_system_test.py
│
├── docker-compose.yml                     # 🐳 Tüm Servisler (8000, 8001, 8002, 3001)
├── docker-compose.gpu.yml                 # 🚀 GPU Hızlandırma
├── ReportLens.sln                         # .NET Solution
├── README.md
└── STRUCTURE.md                           # ✅ Bu Doküman (v2.3)
```

---

## ⚙️ Servis Dağılımı ve Portlar

| Servis Adı | Port | İç Port | Açıklama |
|:---|:---:|:---:|:---|
| `mssql-db` | 1433 | 1433 | Ortak SQL Server 17.0 (Vector Support) |
| `ollama` | 11434 | 11434 | Ortak LLM Motoru |
| `python-api` | 8000 | 8000 | Python Backend & UI |
| `maf-backend` | 8001 | 8080 | .NET API Gateway |
| `maf-llm` | 8002 | 8080 | .NET Agent Microservice |
| `maf-frontend` | 3001 | 80 | .NET Nginx Frontend |
| `adminer` | 8080 | 8080 | DB Yönetim Paneli |

---

## 🚀 Geliştirme Notları

1.  **Prompt Stratejisi:** Tüm ajan talimatları (System Prompts) **İngilizce**'ye çevrilmiştir (Daha iyi akıl yürütme için). Çıkış formatı ise her zaman **Türkçe**'dir.
2.  **Dosya Paylaşımı:** `./ReportLens-Python/Data` klasörü her iki Docker konteyner yapısında ortak volume olarak kullanılır.
3.  **Ajan Izolasyonu:** Ajanlar artık merkezi `ReportLens-LLM` mikroservisinden yönetilmektedir.
