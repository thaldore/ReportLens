"""
Tutarsızlık analizi için sahte veri (anket/metin) üreten ajan.
Seçilen rapor içeriğine dayanarak İKİ AYRI bölüm üretir:
  1. ANKET TABLOSU: Sorular + 1-5 puan + isaretleme (bazi dogru, bazi yanlis)
  2. METIN BEYANLARI: Paragraf halinde iddialar (bazi dogru, bazi yanlis)
"""
from agno.agent import Agent
from agno.models.ollama import Ollama


def create_mock_generator(model: Ollama) -> Agent:
    return Agent(
        model=model,
        description=(
            "Gorevin: Verilen rapor icerigine dayanarak gercekci test verisi uretmek. "
            "Bu veriler daha sonra tutarlilik analizinde rapor ile kiyaslanacak."
        ),
        instructions=[
            "Sana bir rapor icerigi ve Uretim Modu verilecek: Tutarli, Tutarsiz veya Karmasik.",
            "Gorevin TAMAMEN AYRI iki bolum uretmek.",
            "",
            "### BOLUM 1: ANKET TABLOSU",
            "Rapordaki YOKAK kalite kriterlerine uygun 5-7 adet olculebilir kalite sorusu uret.",
            "Her soru icin 1-5 arasi bir puan ve isaretleme yap.",
            "KESINLIKLE asagidaki Markdown tablo formatini kullan:",
            "",
            "## BOLUM 1: ANKET YANITLARI",
            "",
            "| # | Soru | Puan (1-5) | Isaretleme |",
            "| :-- | :--- | :---: | :---: |",
            "| 1 | [Somut kalite sorusu — ornegin: Programlarin AKTS is yukleri belirlenmis mi?] | [1-5] | [X] veya [ ] |",
            "| 2 | [Somut kalite sorusu] | [1-5] | [X] veya [ ] |",
            "",
            "PUAN KURALLARI:",
            "- Mod TUTARSIZ ise: Raporda iyi olan konulara 1-2 puan ver, zayif olanlara 4-5 puan ver. Bazi isaretlemeleri yanlis yap.",
            "- Mod TUTARLI ise: Raporun gercek durumunu yansitan dogru puanlar ve isaretlemeler ver.",
            "- Mod KARMASIK ise: Bazi sorular dogru puanli, bazilari kasitli yanlis olsun.",
            "",
            "### BOLUM 2: METIN BEYANLARI",
            "Rapordaki somut bilgilere dayanan 4-6 maddelik deger/gozlem metni yaz.",
            "Bu bolumu PARAGRAF halinde yaz (tablo degil).",
            "Her cumle bir iddia icermeli: sayi, tarih, birim adi, faaliyet gibi somut bilgiler.",
            "",
            "## BOLUM 2: METIN BEYANLARI",
            "",
            "Ornek format:",
            "[Birim adi] bunyesinde [X adet] program bulunmakta olup, toplam [Y] ogrenci kayitlidir. "
            "[Z] adet TUBITAK projesi yurutulmektedir. Ogretim kadrosu [N] kisiden olusmaktadir. "
            "[Faaliyet/sistem adi] ile performans izlenmektedir.",
            "",
            "METIN KURALLARI:",
            "- Mod TUTARSIZ ise: Kasitli yanlis sayilar, yanlis birim adlari, olmayan faaliyetler ekle.",
            "- Mod TUTARLI ise: Tum bilgiler raporla birebir ortussun.",
            "- Mod KARMASIK ise: Bazi cumleler dogru, bazilari kasitli yanlis olsun.",
            "",
            "### KRITIK KURALLAR:",
            "1. BOLUM 1 (Anket) ve BOLUM 2 (Metin) KESINLIKLE AYRI tutulsun, KARISMASIN.",
            "2. Anket KESINLIKLE Markdown tablo formatinda olsun — duz metin olarak uretme.",
            "3. Metin bolumu PARAGRAF halinde olsun — tablo olarak uretme.",
            "4. Her iki bolumde de rapordaki gercek icerikten ilham al.",
            "5. BOLUM 1 ve BOLUM 2 basliklarini AYNEN kullan, degistirme.",
        ],
    )
