"""
Tutarsızlık analizi için sahte veri (anket/metin) üreten ajan.
Seçilen rapor içeriğine dayanarak tutarlı, tutarsız veya karmaşık veriler üretir.
"""
from agno.agent import Agent
from agno.models.ollama import Ollama

def create_mock_generator(model: Ollama) -> Agent:
    return Agent(
        model=model,
        description="Görevin, verilen rapor içeriğine dayanarak gerçekçi ve amaca uygun sahte anket yanıtları veya metinler üretmektir.",
        instructions=[
            "Sana raporun içeriği ve bir mod (Tutarlı, Tutarsız, Karmaşık) verilecek.",
            "Görevin, iki farklı türde veri üretmektir: 1. Anket Yanıtları (Soru-Cevap), 2. Serbest Analiz Metni.",
            
            "### 1. ANKET YANITLARI (Puanlı Değerlendirme):",
            "- Raporun içeriğiyle ilgili 3-5 adet kalite sorusu üret.",
            "- Her soru için 1'den 5'e kadar bir 'SKOR' ver (Örn: 4/5).",
            "- Bu bölümü mutlaka bir tablo veya liste formatında sun.",
            "- Mod 'Tutarsız' ise puanları rapordaki gerçek başarının tam tersi şekilde üret (Rapor 'çok iyi' diyorsa sen 1-2 puan ver).",

            "### 2. ANALİZ METNİ (Bilgi ve İddialar):",
            "- Raporun içeriğine dair somut iddialar (sayı, tarih, birim adı vb.) içeren bir değerlendirme metni yaz.",
            "- Bu metindeki bilgiler doğru da olabilir, kasten yanlış/hatalı da olabilir (Mod'a göre).",

            "### ÇIKTI FORMATI (ZORUNLU):",
            "**--- ANKET YANITLARI (Değerlendirilmiş) ---**",
            "Soru X: ... | Puan: [1-5] | Değerlendirme Gerekçesi: ...",
            "---",
            "**--- ANALİZ METNİ (Bilgi Durumu) ---**",
            "(Burada raporla ilgili iddialar ve açıklamalar yer alacak...)",
        ],
    )
