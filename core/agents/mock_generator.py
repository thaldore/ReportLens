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
            "Mod 'Tutarlı' ise: Raporla tamamen örtüşen, benzer sayısal veriler ve eylemler içeren bir metin üret.",
            "Mod 'Tutarsız' ise: Raporun temel verilerini (sayılar, birimler, eylemler) kasten yanlış (örn: 5 yerine 15, Kimya yerine Fizik) gösteren bir metin üret.",
            "Mod 'Karmaşık/Karma' ise: Metnin bir kısmı raporla tamamen TUTARLI olsun, fakat bir kısmında kasten TUTARSIZLIK (farklı birim verisi, yanlış sayı veya gerçekleşmeyen eylem) ekle.",
            "Veriyi 'Anket Yanıtları' veya 'Analiz Metni' formatında, sanki bir insan yazmış gibi doğal dilerle üret.",
            "Ürettiğin metnin hangi birime (örn: Biyoloji Bölümü) ait olduğunu mutlaka belirt.",
            "Sadece metni üret, giriş veya sonuç cümlesi (İşte verileriniz: vb.) ekleme.",
        ],
    )
