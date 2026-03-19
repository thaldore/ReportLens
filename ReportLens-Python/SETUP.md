# ReportLens - Yerel LLM Analiz Sistemi Kurulum Rehberi

Bu belge, projeyi sıfırdan kuracak ekip üyeleri için hazırlanmıştır.

## 🤖 İndeksleme ve RAG Çalışma Mantığı

ReportLens, **Agentic RAG (Retrieval-Augmented Generation)** mimarisini kullanır. Yüklediğiniz raporlar şu adımlardan geçer:
1.  **Semantik Parçalama:** Raporlar Markdown başlıklarına göre anlamlı bloklara ayrılır.
2.  **Vektörleştirme (Embedding):** `nomic-embed-text` modeli ile her parça nümerik bir vektöre dönüştürülür.
3.  **İndeksleme:** Bu vektörler yerel **Qdrant** veritabanında saklanır.
4.  **Sorgulama:** Bir soru sorduğunuzda, sistem en alakalı 15-20 parçayı bulur ve LLM'e (llama3.1) "bağlam" olarak sunar.

---

## 🚀 1. Docker ile Hızlı Kurulum (Önerilen)

En sorunsuz ve hızlı yöntem Docker kullanmaktır. Tüm bağımlılıklar ve veritabanları otomatik kurulur.

**Gereksinimler:** Docker Desktop ve NVIDIA Container Toolkit yüklü olmalıdır.

1.  Proje klasöründe terminal açın.
2.  Sistemi ayağa kaldırın:
    ```bash
    docker compose up --build
    ```
3.  **Önemli:** İlk çalıştırmada `llama3.1:8b` ve `nomic-embed-text` modelleri otomatik olarak çekilecektir (yaklaşık 5GB). Bu işlem internet hızınıza bağlı olarak zaman alabilir.
4.  Tarayıcınızda `http://localhost:8501` adresine giderek sistemi kullanmaya başlayın.

---

## 🐍 2. Alternatif: Yerel Python Kurulumu (venv)

Docker kullanmak istemiyorsanız aşağıdaki adımları izleyin.

### A. Ollama Kurulumu
1. [Ollama Windows Download](https://ollama.com/download/windows) adresinden indirin ve kurun.
2. Modelleri manuel çekin:
   ```powershell
   ollama pull llama3.1:8b
   ollama pull nomic-embed-text
   ```

### B. Python Ortamı
1. Sanal ortam oluşturun ve aktif edin:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate
   ```
2. Bağımlılıkları kurun:
   ```powershell
   pip install -r requirements.txt
   ```

### C. Qdrant Çalıştırma
Yerel Python kurulumunda Qdrant'ı ayrıca çalıştırmanız gerekir:
```bash
docker run -p 6333:6333 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

### D. Uygulamayı Başlatma
```powershell
streamlit run ui/main.py
```

---

## 🛠️ 3. Uygulama Akışı

1. **Rapor Yükleme:** `📁 Rapor Yönetimi` sekmesinden PDF/DOCX/Excel/CSV dosyalarını yükleyin.
2. **İşleme ve İndeksleme:** "Yüklenen Dosyaları İşle ve İndeksle" butonuna tıklayın. (Bu işlem metinleri vektör veritabanına kaydeder).
3. **Analiz:** Diğer sekmeleri kullanarak analizleri gerçekleştirin.

## 🧪 4. Testleri Çalıştırma

```powershell
# Venv içindeyken
python -m pytest tests/ -v
```

## 🔐 5. Gizlilik ve Güvenlik

Bu proje tamamen **OFFLINE** çalışır. Hiçbir veri 3. parti servislere (OpenAI, Google vb.) gönderilmez. Tüm analizler kendi donanımınızda (GPU) gerçekleşir.

## ❓ 6. Sorun Giderme

| Sorun | Çözüm |
| :--- | :--- |
| `ConnectionError` | Ollama veya Qdrant konteynerlerinin çalıştığından emin olun. |
| `CUDA out of memory` | GPU belleğiniz (VRAM) yetersiz olabilir. Diğer uygulamaları kapatın. |
| `Boş Sonuçlar` | Raporları yeniden indekslemeyi deneyin. |
| `Docker GPU Hatası` | NVIDIA Container Toolkit'in yüklü olduğunu kontrol edin. |
