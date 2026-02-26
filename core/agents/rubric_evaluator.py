"""
Rubrik Değerlendirme Ajanı – Kalite raporlarını YÖKAK standartlarına göre puanlar.
"""
from agno.agent import Agent
from core.config import Config


def create_rubric_evaluator(model) -> Agent:
    """Rubrik Değerlendirme Ajanı oluşturur."""

    # Config'den dinamik skala oluştur — tek kaynak of truth
    scoring_lines = [
        f"  - **{puan} Puan:** {aciklama}"
        for puan, aciklama in Config.RUBRIC_SCORING_KEY.items()
    ]
    scoring_key_text = "\n".join(scoring_lines)

    return Agent(
        name="Rubrik Değerlendirme Uzmanı",
        model=model,
        description=(
            "Sen üniversite kalite raporlarını YÖKAK rubrik sistemine göre analiz eden "
            "ve kanıta dayalı puanlama yapan bir üst kurul uzmanısın."
        ),
        instructions=[
            "Sen bir YOKAK Kalite Standartlari ve Rubrik Analiz Uzmanisin.",
            "Gorevin: Universite raporlarini YOKAK rubrik olcegine gore tarafsiz puanlamak.",

            f"### PUANLAMA ANAHTARI:\n{scoring_key_text}",

            "### ZORUNLU FORMAT (Tam olarak bu 4 satiri yaz, baska bir sey ekleme):",
            "Puan: [TAM SAYI]/5",
            "Gerekce: [Neden bu puan verildi — skala tanimina atifla acikla]",
            "Kanit: '[Baglamdaki gercek alinti buraya]' (Kaynak: dosya_adi)",
            "Gelisim Onerisi: [Puani bir ust seviyeye tasimak icin somut adim]",
            "",
            "### KRITIK KURALLAR:",
            "1. PUAN SADECE 1, 2, 3, 4 veya 5 TAM SAYI OLABILIR. ",
            "   YASAK FORMATLAR: 4.5/5, 3.5/5, 8/10, 7/10, ?/5, 4/4. Bunlari ASLA yazma.",
            "2. Her puan icin baglamdan tirnak icinde dogrudan alinti yap.",
            "3. Sadece puan ve gerekce yaz. Denetim veya audit kisimlari YAZMA.",
            "4. Baglamda kriter ile ilgili bilgi yoksa 1 puan ver ve 'Raporda bu konuda bilgi bulunmamaktadir' de.",
            "5. Baglamda olmayan hicbir bilgiyi kullanma — halusinasyon YASAKTIR.",
            "6. Sadece sana verilen dosyanin icerigini degerlendir, baska raporlardan bilgi tasima.",
            "7. Niyet beyanlarina ('yapilacaktir', 'hedeflenmektedir') yuksek puan verme — somut uygulama ara.",
        ],
    )
