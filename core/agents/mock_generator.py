"""
Tutarsızlık analizi için sahte veri (anket/metin) üreten ajan.
Seçilen rapor içeriğine dayanarak AYRI bölümler halinde anket tablosu ve analiz metni üretir.
"""
from agno.agent import Agent
from agno.models.ollama import Ollama


def create_mock_generator(model: Ollama) -> Agent:
    return Agent(
        model=model,
        description=(
            "Görevin, verilen rapor içeriğine dayanarak gerçekçi ve amaca uygun "
            "iki AYRI bölüm üretmektir: (1) Markdown tablo formatında anket ve (2) analiz metni."
        ),
        instructions=[
            "Sana bir rapor içeriği ve Üretim Modu verilecek: Tutarlı, Tutarsız veya Karmaşık.",
            "Görevin TAMAMEN AYRI iki bölüm üretmektir.",

            "### BÖLÜM 1 — ANKET YANITLARI:",
            "Raporun YÖKAK kalite kriterlerine uygun 4-5 adet ölçülebilir kalite sorusu üret.",
            "Bu bölümü AŞAĞIDAKİ Markdown tablosu formatında üret (başka format kullanma):",
            "| # | Soru | Puan (1-5) | Gerekçe |",
            "| :-- | :--- | :---: | :--- |",
            "| 1 | [Somut kalite sorusu] | [1-5] | [Neden bu puan verildi] |",
            "Mod TUTARSIZ ise: Raporda iyi durum bildirilen konulara 1-2, zayıf bildirilen konulara 4-5 puan ver.",
            "Mod TUTARLI ise: Raporun gerçek durumunu yansıtan doğru puanlar ver.",
            "Mod KARMAŞIK ise: Bazı sorular tutarlı (rapor gibi), bazıları tutarsız (ters puan) olsun.",

            "### BÖLÜM 2 — ANALİZ METNİ:",
            "Raporun gerçek içeriğindeki somut bilgilere atıfta bulunan 4-6 maddelik değerlendirme yaz.",
            "Her madde; bir iddia veya gözlem içermelidir: sayı, tarih, birim adı, faaliyet gibi somut bilgiler.",
            "Mod TUTARSIZ ise: Bazı maddelerde kasten yanlış veri üret (sayıyı değiştir, yanlış birim adı kullan).",
            "Mod TUTARLI ise: Tüm maddeler raporla örtüşsün.",
            "Mod KARMAŞIK ise: Kasıtlı olarak bazı doğru, bazı yanlış maddeler yaz.",

            "### ZORUNLU ÇIKTI FORMATI (asla değiştirme):",
            "## BÖLÜM 1 — ANKET YANITLARI",
            "| # | Soru | Puan (1-5) | Gerekçe |",
            "| :-- | :--- | :---: | :--- |",
            "| 1 | [soru] | [1-5] | [gerekçe] |",
            "",
            "## BÖLÜM 2 — ANALİZ METNİ",
            "- Madde 1: [somut iddia veya gözlem]",
            "- Madde 2: ...",

            "### KRİTİK KURALLAR:",
            "1. Bölüm 1 (Anket Tablosu) ve Bölüm 2 (Metin) KESINLIKLE ayrı tutulsun, karışmasın.",
            "2. Anket tablosu kesinlikle Markdown tablo formatında olsun — liste veya düz metin olarak üretme.",
            "3. Her bölüm için rapordaki gerçek içerikten ilham al, raporda olmayan bilgi uydurma.",
            "4. Metin bölümünde raporda geçen gerçek sayıları, isimleri ve tarihleri kullan.",
        ],
    )
