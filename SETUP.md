# ReportLens - Yerel LLM Analiz Sistemi Kurulum Rehberi

Bu belge, projeyi sıfırdan kuracak ekip üyeleri için hazırlanmıştır.

## 1. Sistem Gereksinimleri
- **Python:** 3.10+
- **GPU:** NVIDIA RTX serisi (Min. 8GB VRAM)
- **RAM:** Min. 16GB (32GB önerilir)
- **Disk:** Min. 10GB boş alan (model + vektör veritabanı)
- **İnternet:** Sadece ilk kurulumda (model ve kütüphane indirme)

## 2. Ollama Kurulumu

Ollama, yerel modelleri çalıştırmak için gereken ana motordur.

1. [Ollama Windows Download](https://ollama.com/download/windows) adresinden `OllamaSetup.exe` indirin ve kurun
2. Sistem tepsisinde (sağ alt köşe) Ollama ikonunun göründüğünü doğrulayın
3. Terminal açıp kurulumu doğrulayın:
   ```powershell
   ollama --version
   ```

## 3. Python Sanal Ortam Kurulumu

1. Proje klasörüne (`ReportLens`) terminal ile gidin
2. Sanal ortam oluşturun:
   ```powershell
   python -m venv venv
   ```
3. Sanal ortamı aktif edin:
   ```powershell
   .\venv\Scripts\Activate
   ```
   > Aktif olduğunda satır başında `(venv)` görünmelidir.
4. Bağımlılıkları kurun:
   ```powershell
   pip install -r requirements.txt
   ```

## 4. Model İndirme

Sanal ortam aktifken şu komutları çalıştırın:

```powershell
# Ana LLM modeli (Yaklaşık 4.7 GB)
ollama pull llama3.1:8b

# Embedding modeli (Yaklaşık 270 MB)
ollama pull nomic-embed-text
```

## 5. Uygulamayı Başlatma

```powershell
# Sanal ortam aktif olmalı (venv)
streamlit run ui/main.py
```

Tarayıcınızda `http://localhost:8501` adresinde uygulama açılacaktır.

## 6. Uygulama Akışı

1. **Rapor Yükleme:** `📁 Rapor Yönetimi` sekmesinden PDF/DOCX/Excel/CSV dosyalarını yükleyin
2. **İşleme ve İndeksleme:** "Yüklenen Dosyaları İşle ve İndeksle" butonuna tıklayın
3. **Analiz:** Diğer sekmeleri kullanarak raporlarınızı analiz edin:
   - 🤖 **Kalite Analiz Uzmanı** — Serbest metin sorguları
   - 📄 **Rapor Analizi** — Tekil rapor detaylı analizi
   - 📊 **Öz Değerlendirme** — Kapsamlı YÖKAK raporu üretimi
   - ⚖️ **Rubrik Notlandırma** — YÖKAK rubrik puanlama
   - 🔍 **Tutarsızlık Analizi** — Beyan/anket doğrulama

## 7. Testleri Çalıştırma

```powershell
# Tüm testler
python -m pytest tests/ -v

# Belirli test dosyası
python -m pytest tests/test_output_validator.py -v
```

## 8. Gizlilik ve Güvenlik

Bu proje tamamen **OFFLINE** çalışır:
- LLM modeli yerel çalışır (Ollama)
- Vektör veritabanı yerel diskte saklanır (Qdrant)
- Veriler `Data/` dizininde tutulur
- Hiçbir veri 3. parti servislere gönderilmez

## 9. Sorun Giderme

| Sorun | Çözüm |
| :--- | :--- |
| `ConnectionError: Ollama'ya bağlanılamıyor` | Ollama'nın çalıştığından emin olun (sistem tepsisi) |
| `Model bulunamadı` | `ollama pull llama3.1:8b` çalıştırın |
| `Embedding hatası` | `ollama pull nomic-embed-text` çalıştırın |
| `CUDA out of memory` | Diğer GPU kullanan uygulamaları kapatın |
| Boş analiz sonuçları | `📁 Rapor Yönetimi`'nden dosyaları yeniden işleyin |
