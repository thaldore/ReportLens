# ReportLens — Modül Beklenen Çıktı Spesifikasyonu

Bu doküman, sistemdeki her modülün **doğru çıktı formatını**, beklenen davranışını ve kalite kriterlerini tanımlar.
İlerde geliştirme yapılırken bu doküman **referans standart** olarak kullanılmalıdır.

---

## 1. 🤖 Kalite Analiz Uzmanı (RAG Sohbet)

### Amaç
Kullanıcının serbest metin sorusunu alır, vektör veritabanından ilgili rapor bölümlerini çeker ve bağlama dayalı analiz üretir.

### Beklenen Çıktı Yapısı

```
## 1. BİRİM / KONU
[Analiz edilen birim ve konu — 1-2 cümle]

## 2. TEMEL BULGULAR
- Bulgu 1: [somut veri — sayı/tarih/isim] (Kaynak: dosya_adi)
- Bulgu 2: [somut veri] (Kaynak: dosya_adi)
- Bulgu 3: [somut veri] (Kaynak: dosya_adi)
- Bulgu 4: [somut veri] (Kaynak: dosya_adi)

## 3. GÜÇLÜ YÖNLER
- [güçlü yön + kanıt] (Kaynak: dosya_adi)

## 4. GELİŞİME AÇIK ALANLAR
- [zayıf yön + açıklama]

## 5. ÖNERİLER
- [öneri + beklenen fayda]
```

### Kalite Kriterleri
| Kriter | Beklenen | Kabul Edilemez |
| :--- | :--- | :--- |
| Kaynak gösterimi | Her bulgunun sonunda `(Kaynak: dosya_adi)` | Kaynaksız iddia |
| Halüsinasyon | Sadece bağlamdaki veriler kullanılır | Bağlamda olmayan isim/sayı/proje |
| Birim izolasyonu | Sadece sorulan birimin verileri | Farklı birimden veri karışması |
| Veri yoksa davranış | "Bu konuda bağlamda yeterli veri bulunamamıştır" | Uydurma veri veya genel bilgi |
| Dil | Akademik, yapıcı Türkçe | Belirsiz ifadeler ("muhtemelen", "olabilir") |

---

## 2. 📄 Rapor Analizi (Tekil Rapor)

### Amaç
Seçilen tek bir raporun tüm chunk'larını alır ve 6 bölümlük kapsamlı analiz üretir.

### Beklenen Çıktı Yapısı

```
## 1. Rapor Türü ve Kapsamı
- Raporun türü: [dosya metadata'sından alınır — ÖDR/Eylem Planı/Tutanak/Akran vb.]
- Birim: [metadata'dan]
- Yıl/Dönem: [metadata'dan]

## 2. Temel Sayısal Veriler
- Öğrenci sayıları: [rapordaki gerçek rakamlar]
- Program sayısı: [rapordaki gerçek rakam]
- Proje/yayın sayısı: [rapordaki gerçek rakam]
- Anket sonuçları: [rapordaki gerçek rakam]
⚠️ Raporda bu veriler bulunamamıştır. [veri yoksa]

## 3. Ana Bulgular
- Bulgu 1: [somut kanıtla]
- Bulgu 2: [somut kanıtla]
- Bulgu 3: [somut kanıtla]
- Bulgu 4: [somut kanıtla]

## 4. Güçlü Yönler
- [olumlu alan + rapordaki kanıt]

## 5. Zayıf Yönler / Gelişim Alanları
- [eksik/sorunlu alan + rapordaki kanıt]

## 6. Eylem / Hedefler
- [hedef/eylem + sorumlu + süre] (raporda varsa)
```

### Kalite Kriterleri
| Kriter | Beklenen | Kabul Edilemez |
| :--- | :--- | :--- |
| Rapor türü | Metadata'dan otomatik alınır | LLM'in tahmin etmesi |
| Sayısal veriler | Rapordaki birebir rakamlar | Yuvarlama veya uydurma |
| Chunk sırası | `chunk_index`'e göre sıralı | Karışık sıra |
| Veri yoksa davranış | "Raporda bu veri bulunamamıştır" | Soru sorma veya yönerge verme |
| Analiz derinliği | Her bölüm en az 3-4 madde | Tek satır veya boş bölüm |

---

## 3. 📊 Öz Değerlendirme Raporu Oluşturucu

### Amaç
Birden fazla kalite raporundan 6 kriterin analizini yaparak YÖKAK yapısına uygun kapsamlı rapor üretir.

### Beklenen Çıktı Yapısı (YÖKAK 7 Bölüm)

```
# [BİRİM ADI] ÖZ DEĞERLENDİRME RAPORU [YIL]

## 1. YÖNETİCİ ÖZETİ
[En az 2 paragraf — birim adı, dönem, ana güçlü yönler, gelişim alanları]

## 2. A. LİDERLİK, YÖNETİŞİM VE KALİTE
### 2.1 Yönetim Yapısı ve Karar Alma Süreçleri
### 2.2 Stratejik Planlama
### 2.3 Paydaş Katılımı
### 2.4 Kalite Güvence Mekanizmaları

## 3. B. EĞİTİM VE ÖĞRETİM
### 3.1 Program Yapısı ve Öğrenci Verileri
### 3.2 Öğrenci Merkezli Öğretim
### 3.3 Öğretim Kadrosu
### 3.4 Ölçme ve Değerlendirme

## 4. C. ARAŞTIRMA VE GELİŞTİRME
### 4.1 Araştırma Politikası
### 4.2 Projeler ve Yayınlar
### 4.3 Performans İzleme

## 5. D. TOPLUMSAL KATKI
### 5.1 Dış Paydaş ve Sektör İşbirlikleri
### 5.2 Sosyal Sorumluluk

## 6. GÜÇLÜ YÖNLER VE GELİŞİM ALANLARI
| Güçlü Yönler | Gelişim Alanları |
| :--- | :--- |
| [somut kanıt ile] | [somut eksiklik ile] |

## 7. SONUÇ VE EYLEM PLANI
| Eylem | Sorumlu | Süre | Beklenen Sonuç |
| :--- | :--- | :--- | :--- |
```

### Kalite Kriterleri
| Kriter | Beklenen | Kabul Edilemez |
| :--- | :--- | :--- |
| Bölüm yapısı | 7 bölümün tamamı mevcut | Eksik bölüm veya farklı yapı |
| Her bölüm derinliği | En az 3 somut veri noktası | Tek cümle veya boş bölüm |
| Tekrar | Her bölüm benzersiz içerik | Aynı paragrafın farklı bölümlerde tekrarı |
| Yönlendirme | Mevcut durumu raporla | "Şunları yapın" tarzı tavsiyeler |
| Birim adı tutarlılığı | Tüm rapor boyunca aynı ad | Farklı bölümlerde farklı isim |
| Sayısal veri | Sadece bağlamdaki veriler | Uydurma istatistikler |

---

## 4. ⚖️ Rubrik Notlandırma Sistemi

### Amaç
Raporları YÖKAK rubrik kriterlerine (A-D) göre 1-5 arası puanlar. İki aşamalı: Evaluator puanlar → Validator bağımsız olarak denetler.

### Beklenen Çıktı Yapısı

```
# 📊 Rubrik Notlandırma Raporu

**Değerlendirilen Raporlar:** dosya1.md, dosya2.md

## 📄 Rapor: dosya1.md

### 📏 A. Liderlik, Yönetişim ve Kalite

Puan: [1-5 tam sayı]/5
Gerekçe: [skala tanımına atıfla açıklama]
Kanıt: '[rapordaki gerçek alıntı]' (Kaynak: dosya_adi)
Gelişim Önerisi: [somut adım]

#### 🛡️ DENETİM
Karar: ONAYLANDI veya HATALI BULUNDU
Bağımsız Puan: [1-5]/5
Gözlem: [kanıt doğrulama + tutarlılık]
Sonuç: Puan [X]/5 olmalıdır — [kısa gerekçe]

----------------------------------------

### 📋 dosya1.md — Özet Puan Tablosu

| Kriter | Değerlendirici Puanı | Denetçi Puanı | Denetim Kararı |
| :--- | :---: | :---: | :---: |
| A. Liderlik | 3/5 | 3/5 | ✅ Onay |
| B. Eğitim | 2/5 | 2/5 | ✅ Onay |
| C. Araştırma | 3/5 | 2/5 | ❌ Düzeltme |
| D. Toplumsal | 2/5 | 2/5 | ✅ Onay |
```

### Kalite Kriterleri
| Kriter | Beklenen | Kabul Edilemez |
| :--- | :--- | :--- |
| Puan formatı | Tam sayı 1-5 arası | 4.5/5, 8/10, ?/5 |
| Puan dağılımı | Çoğu 2-3, nadiren 4-5 | Hep 4/5 (pozitif bias) |
| Kanıt alıntısı | Rapordaki gerçek cümle (tırnak içinde) | Uydurma veya genel ifade |
| Denetçi bağımsızlığı | Evaluator puanını görmeden puanlar | Evaluator puanını onaylama eğilimi |
| 4-5 puan koşulu | Sadece somut PUKÖ kanıtı varsa | Niyet beyanlarına yüksek puan |
| Puan bulunamazsa | "Değerlendirilemedi" | ?/5 yazma |

### Puanlama Skalası (YÖKAK Uyumlu)
| Puan | Tanım |
| :---: | :--- |
| 1 | Hiç Yok — İlgili konuda hiçbir planlama veya uygulama yok |
| 2 | Planlama/Niyet — Niyet veya plan var, somut uygulama yok |
| 3 | Uygulama — En az bir somut uygulama örneği mevcut |
| 4 | İzleme — Uygulama + sonuçları düzenli takip ediliyor |
| 5 | Sürekli İyileştirme — PUKÖ döngüsü tamamlanmış, iyileştirmeler yapılmış |

---

## 5. 🔍 Tutarsızlık Analizi

Bu modül iki alt bileşenden oluşur: **Sahte Veri Üretici** ve **Tutarsızlık Denetçisi**.

### 5A. Sahte Veri Üretici (Mock Generator)

#### Amaç
Seçilen raporun içeriğine dayanarak test verisi üretir (anket + metin). 3 mod: Tutarlı / Tutarsız / Karmaşık.

#### Beklenen Çıktı Yapısı

```
## BÖLÜM 1: ANKET YANITLARI

| # | Soru | Puan (1-5) | İşaretleme |
| :-- | :--- | :---: | :---: |
| 1 | [YÖKAK kalite sorusu] | [1-5] | [X] veya [ ] |
| 2 | [YÖKAK kalite sorusu] | [1-5] | [X] veya [ ] |
| ... | ... | ... | ... |

## BÖLÜM 2: METİN BEYANLARI

[Birim adı] bünyesinde [X adet] program bulunmakta olup, toplam [Y] öğrenci
kayıtlıdır. [Z] adet TÜBİTAK projesi yürütülmektedir...

[GT:DOGRU] veya [GT:YANLIS] — her iddia için gizli ground truth etiketi
```

#### Mod Davranışları
| Mod | Anket | Metin |
| :--- | :--- | :--- |
| Tutarlı | Rapordaki durumu yansıtan doğru puanlar | Tüm bilgiler raporla birebir örtüşür |
| Tutarsız | İyi olan konulara düşük, zayıf olanlara yüksek puan | Kasıtlı yanlış sayılar ve bilgiler |
| Karmaşık | Bazı sorular doğru, bazıları kasıtlı yanlış | Bazı cümleler doğru, bazıları yanlış |

---

### 5B. Tutarsızlık Denetçisi (Consistency Checker)

#### Amaç
Rapor içeriğini (mutlak doğru) ile kullanıcı beyanlarını (anket + metin) karşılaştırarak her iddiayı etiketler.

#### Beklenen Çıktı Yapısı

```
## ANALİZ 1: RAPOR ÖZETİ
- Birim: [rapordaki birim adı]
- Dönem: [rapordaki yıl/dönem]
- Önemli Veriler:
  - [sayısal veri 1]
  - [sayısal veri 2]
  - [sayısal veri 3]

## ANALİZ 2: ANKET YANITLARININ DOĞRULANMASI

### Soru 1: [Soru metni]
- Verilen Puan: [X/5]
- Rapordaki Gerçek: "[doğrudan alıntı]"
- SONUÇ: DOĞRU | YANLIŞ | BİLGİ YOK
- Güven: HIGH | MEDIUM | LOW
- Açıklama: [neden bu sonuç]

### Soru 2: [Soru metni]
...

## ANALİZ 3: METİN BEYANLARININ DOĞRULANMASI

### İddia 1: '[iddia metni]'
- Rapordaki Gerçek: "[alıntı]"
- SONUÇ: DOĞRU | YANLIŞ | BİLGİ YOK
- Güven: HIGH | MEDIUM | LOW
- Açıklama: [açıklama]

### İddia 2: '[iddia metni]'
...

## ÖZET TABLOSU

| # | Kaynak | İddia/Beyan | Rapordaki Gerçek | SONUÇ | Güven |
| :-- | :--- | :--- | :--- | :---: | :---: |
| 1 | Anket S1 | [iddia] | [gerçek] | DOĞRU | HIGH |
| 2 | Anket S2 | [iddia] | [gerçek] | YANLIŞ | HIGH |
| 3 | Metin 1 | [iddia] | [gerçek] | BİLGİ YOK | LOW |
```

#### Kalite Kriterleri
| Kriter | Beklenen | Kabul Edilemez |
| :--- | :--- | :--- |
| Rapor kaynağı | Mutlak doğru kabul edilir | Rapor bilgisini sorgulama |
| İddia bazlı analiz | Her iddia AYRI AYRI analiz edilir | Toplu değerlendirme |
| Etiketleme | BÜYÜK HARFLERLE: DOĞRU / YANLIŞ / BİLGİ YOK | Küçük harf veya farklı format |
| Güven seviyesi | HIGH / MEDIUM / LOW | Sayısal değer (0.73 gibi) |
| YANLIŞ ise | Doğru değer MUTLAKA belirtilir | Sadece "yanlış" demek |
| BİLGİ YOK ise | Raporda bilgi olmadığı belirtilir | Tahmin yapma |
| Özet tablo | Tüm analizlerin tablosu | Tablo eksik |

---

## 6. 🛡️ Output Validation (Post-Processing Katmanı)

Tüm modül çıktıları kullanıcıya gösterilmeden önce aşağıdaki doğrulamalardan geçer:

### Halüsinasyon Dedektörü
- Çıktıdaki sayısal değerleri bağlamda arar
- Bağlamda geçmeyen sayılar için `⚠️ Doğrulanmamış veri` uyarısı ekler

### Format Doğrulama
- Beklenen bölüm başlıklarının var olduğunu kontrol eder
- Eksik bölümler için `⚠️ Bu bölüm oluşturulamadı` mesajı ekler

### Tekrar Dedektörü
- Paragraf bazlı benzerlik kontrolü (jaccard)
- %80+ benzerlik varsa tekrarlı paragrafı kaldırır

### Puan Format Doğrulama (Rubrik)
- `[1-5]/5` formatını zorlar
- Parse edilemeyen puanlar için "Değerlendirilemedi" yazar

---

## 7. 📁 Genel Sistem Kuralları

### Halüsinasyon Politikası
1. Tüm modüller SADECE bağlam verilerini kullanır
2. Bağlamda olmayan bilgi EKLENMEZ
3. Sayı uydurmak KESİNLİKLE YASAKTIR
4. Veri yoksa "Bu konuda bağlamda yeterli veri bulunamamıştır" yazılır

### Metadata Kullanımı
- Rapor türü, birim adı ve yıl bilgisi dosya adından parse edilir
- Bu bilgiler her prompt'a otomatik eklenir
- LLM'in bu bilgileri tahmin etmesi engellenir

### Birim İzolasyonu
- Her analiz sadece ilgili birimin verilerini kullanır
- Farklı birimden veri karışması filtreleme ile engellenir

### Veri Gizliliği
- Tüm işlem yerel yapılır (Ollama + Qdrant yerel)
- 3. parti bulut servisine veri çıkışı yoktur
- Veriler `Data/` dizininde saklanır
