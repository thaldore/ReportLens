# ReportLens - Yerel LLM Analiz Sistemi Kurulum Rehberi

Bu belge, projeyi sıfırdan kuracak ekip üyeleri için hazırlanmıştır.

## 1. Sistem Gereksinimleri ve Hazırlık
- **Python:** 3.10.11 
- **GPU:** NVIDIA RTX serisi (Min. 8GB VRAM önerilir).
- **İnternet:** Sadece model ve kütüphane kurulumu sırasında gereklidir.

## 2. Ollama Kurulumu (Adım Adım)
Ollama, yerel modelleri çalıştırmak için gereken ana motordur.
1. [Ollama Windows Download](https://ollama.com/download/windows) adresine gidin.
2. `OllamaSetup.exe` dosyasını indirin ve kurun.
3. Kurulum bittikten sonra sağ alt köşede (sistem tepsisi) Ollama ikonunun göründüğünden emin olun.
4. Terminali (PowerShell veya CMD) açıp `ollama --version` yazarak kurulumu doğrulayın.

## 3. Python Sanal Ortam (venv) Kurulumu
Python 3.10.11 bilgisayarınızda yüklü olduğu için projeye özel bir izole alan oluşturacağız. Bu işlem Python'u tekrar indirmeyi gerektirmez.

1. Proje klasörüne (`ReportLens`) terminal ile gidin.
2. Şu komutu çalıştırarak sanal ortamı oluşturun:
   ```powershell
   python -m venv venv
   ```
3. Sanal ortamı aktif edin:
   ```powershell
   .\venv\Scripts\Activate
   ```
   *Not: Aktif olduğunda terminal satırının başında `(venv)` ibaresini görmelisiniz.*
4. Gerekli kütüphaneleri kurun:
   ```powershell
   pip install -r requirements.txt
   ```

## 4. Model ve Agent Hazırlığı
Terminaliniz aktifken (`venv` içindeyken) şu komutları çalıştırın:

```powershell
# Ana modeli indirme (Yaklaşık 4.7 GB)
ollama pull llama3.1:8b

# Raporlama Uzmanı Agent rolünü sisteme kaydetme
ollama create quality-expert -f models/reporter_expert.Modelfile
```

## 5. Uygulama Akışı
Her şey kurulduktan sonra analiz süreci şu şekilde işler:
1. **Veri Girişi:** PDF/DOCX dosyalarını `Data/raw_data` içine atın.
2. **İşleme:** Raporları Markdown'a çevirin: `python scripts/process_data.py`
3. **Analiz:** Raporları sorgulayın: `python scripts/analyze_reports.py`

## 6. Gizlilik ve Güvenlik
Bu proje tamamen **OFFLINE** çalışacak şekilde tasarlanmıştır. Verileriniz asla dışarı çıkmaz, vektör veritabanınız (`Data/vector_db`) yerel diskinde saklanır.
