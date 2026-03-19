# ReportLens: Akıllı Kalite Raporu Analiz ve Yönetim Sistemi

ReportLens, üniversite kalite raporlarını (YÖKAK standartları vb.) analiz eden, tutarsızlıkları denetleyen ve özet raporlar üreten yerel bir AI sistemidir.

## Proje Yapısı

Proje iki ana ekosistemden oluşmaktadır:

1. **[ReportLens-Python](./ReportLens-Python/)**: Mevcut çalışan, Python (Agno/Ollama) tabanlı ajan orkestrasyon ve analiz sistemi.
2. **[ReportLens-Microsoft-Agent-Framework](./ReportLens-Microsoft-Agent-Framework/)**: .NET tabanlı, Microsoft Semantic Kernel kullanan, Clean Architecture prensiplerine uygun yeni nesil yapı.

## Ortak Temel Prensipler

- **Yerel Öncelikli (Local-First)**: Verileriniz asla dışarı çıkmaz. Ollama ve MSSQL yerel sunucularda çalışır.
- **MSSQL Vektör Veritabanı**: Her iki ekosistem de SQL Server 2022+ vektör yeteneklerini kullanarak verileri yönetir.
- **Sürdürülebilirlik**: Modüler yapı sayesinde ölçeklenebilir ve kolay bakım yapılabilir bir mimari.

## Hızlı Başlangıç

- Python ortamı için: `cd ReportLens-Python` ve `SETUP.md` dosyasını inceleyin.
- .NET ortamı için: `cd ReportLens-Microsoft-Agent-Framework` içindeki modülleri inceleyin.

---
© 2026 ReportLens - Tüm Hakları Saklıdır.
