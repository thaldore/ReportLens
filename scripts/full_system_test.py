"""
ReportLens Kapsamlı Sistem Testi.
Tüm 5 modülü test eder ve ham çıktıları tek bir Markdown dosyasına kaydeder.
Puanlama YAPMAZ — sadece Streamlit'teki gibi ham çıktıları kaydeder.

Docker ile çalıştırma:
    docker compose exec streamlit python scripts/full_system_test.py
    docker compose exec streamlit python scripts/full_system_test.py --module kalite

Yerel çalıştırma:
    python scripts/full_system_test.py
    python scripts/full_system_test.py --module rapor --count 5
"""
import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

# Proje kökünü path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import Config
from core.logging_config import get_logger

logger = get_logger(__name__)


class TestOutputCollector:
    """Tüm test çıktılarını toplar ve kaydetmeye hazırlar."""

    def __init__(self):
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.sections = []  # (başlık, çıktı) listesi
        self.summary = {
            "total": 0,
            "success": 0,
            "error": 0,
            "modules": {},
        }

    def add(self, module: str, test_name: str, output: str, duration: float, error: str = None):
        """Bir test sonucunu ekler."""
        self.summary["total"] += 1
        if module not in self.summary["modules"]:
            self.summary["modules"][module] = {"tests": 0, "errors": 0}
        self.summary["modules"][module]["tests"] += 1

        if error:
            self.summary["error"] += 1
            self.summary["modules"][module]["errors"] += 1
            section = (
                f"### ❌ {test_name}\n\n"
                f"**Süre:** {duration:.1f} saniye\n\n"
                f"**Hata:** {error}\n"
            )
        else:
            self.summary["success"] += 1
            section = (
                f"### ✅ {test_name}\n\n"
                f"**Süre:** {duration:.1f} saniye\n\n"
                f"{output}\n"
            )

        self.sections.append((module, section))

    def save(self) -> str:
        """Tüm sonuçları tek bir Markdown dosyasına kaydeder."""
        Config.ensure_directories()

        # Markdown rapor oluştur
        lines = []
        lines.append(f"# 📊 ReportLens Kapsamlı Test Raporu\n")
        lines.append(f"**Tarih:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"**Toplam Test:** {self.summary['total']} | "
                      f"**Başarılı:** {self.summary['success']} | "
                      f"**Hata:** {self.summary['error']}\n")

        # Modül özeti
        lines.append("\n## 📋 Modül Özeti\n")
        lines.append("| Modül | Test Sayısı | Hata |")
        lines.append("| :--- | :---: | :---: |")
        for mod, data in self.summary["modules"].items():
            lines.append(f"| {mod} | {data['tests']} | {data['errors']} |")

        lines.append("\n---\n")

        # Modül bazlı çıktılar
        current_module = None
        for module, section in self.sections:
            if module != current_module:
                current_module = module
                lines.append(f"\n## 🔹 {module}\n")
            lines.append(section)
            lines.append("\n---\n")

        # Dosyaya kaydet
        md_content = "\n".join(lines)
        md_path = Config.TEST_RESULTS_DIR / f"test_raporu_{self.run_id}.md"
        md_path.write_text(md_content, encoding="utf-8")

        # JSON olarak da kaydet (Streamlit tarafından okunacak)
        json_data = {
            "run_id": self.run_id,
            "tarih": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "toplam_test": self.summary["total"],
            "basarili": self.summary["success"],
            "hata": self.summary["error"],
            "moduller": {
                mod: {"test": data["tests"], "hata": data["errors"]}
                for mod, data in self.summary["modules"].items()
            },
        }
        json_path = Config.TEST_RESULTS_DIR / f"test_results_{self.run_id}.json"
        json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"Test raporu kaydedildi: {md_path}")
        return str(md_path)


def get_available_reports() -> list:
    """Veritabanındaki raporları listeler."""
    md_files = list(Config.PROCESSED_DATA_DIR.glob("*.md"))
    return [f.name for f in md_files]


# ── Modül Test Fonksiyonları ──────────────────────────────────────

def run_kalite_tests(brain, collector: TestOutputCollector, count: int = 10):
    """Kalite Analiz Uzmanı — 10 farklı soru."""
    queries = [
        ("Fen Fakültesi eğitim kalitesi nasıl?", None, None),
        ("IIBF araştırma performansı nedir?", None, None),
        ("Mimarlık Fakültesi paydaş katılımı nasıl?", None, None),
        ("Öğrenci memnuniyeti nasıl?", "Fen", None),
        ("Kalite güvence mekanizmaları nelerdir?", "IIBF", None),
        ("Uluslararasılaşma çalışmaları nelerdir?", "ITBF", None),
        ("2024 yılı performans değerlendirmesi", "Fen", "2024"),
        ("2025 stratejik hedefler gerçekleşme durumu", "IIBF", "2025"),
        ("Fen Fakültesi 2024 eylem planı izleme sonuçları nelerdir?", None, None),
        ("IIBF mezun takip sistemi ve işe yerleşme oranları", None, None),
    ]

    for i, (query, birim, yil) in enumerate(queries[:count]):
        test_name = f"KA-{i+1}: {query[:60]}"
        print(f"  ⏳ {test_name}")
        start = time.time()
        try:
            result, auto_birim, auto_yil = brain.analyze(query, birim=birim, yil=yil)
            duration = time.time() - start

            # Filtre bilgisini çıktıya ekle
            header = ""
            if auto_birim or auto_yil or birim or yil:
                parts = []
                if birim or auto_birim:
                    parts.append(f"Birim: **{birim or auto_birim}**")
                if yil or auto_yil:
                    parts.append(f"Yıl: **{yil or auto_yil}**")
                header = f"🔍 Filtre: {', '.join(parts)}\n\n"

            collector.add("Kalite Analiz Uzmanı", test_name, header + result, duration)
            print(f"  ✅ {test_name} ({duration:.1f}s)")
        except Exception as e:
            collector.add("Kalite Analiz Uzmanı", test_name, "", time.time() - start, str(e))
            print(f"  ❌ {test_name} — Hata: {e}")


def run_rapor_tests(brain, collector: TestOutputCollector, count: int = 15):
    """Rapor Analizi — 15 rastgele rapor."""
    reports = get_available_reports()
    if not reports:
        print("  ⚠️ Analiz edilecek rapor bulunamadı!")
        return

    # Her birimden dengeli seçim
    birim_groups = {}
    for r in reports:
        birim = r.split("_")[0] if "_" in r else "Diger"
        birim_groups.setdefault(birim, []).append(r)

    selected = []
    per_birim = max(count // max(len(birim_groups), 1), 2)
    for group in birim_groups.values():
        random.shuffle(group)
        selected.extend(group[:per_birim])

    remaining = [r for r in reports if r not in selected]
    random.shuffle(remaining)
    selected.extend(remaining[:max(0, count - len(selected))])

    for i, filename in enumerate(selected[:count]):
        test_name = f"RA-{i+1}: {filename}"
        print(f"  ⏳ {test_name}")
        start = time.time()
        try:
            result = brain.analyze_single_report(filename)
            duration = time.time() - start
            collector.add("Rapor Analizi", test_name, result, duration)
            print(f"  ✅ {test_name} ({duration:.1f}s)")
        except Exception as e:
            collector.add("Rapor Analizi", test_name, "", time.time() - start, str(e))
            print(f"  ❌ {test_name} — Hata: {e}")


def run_oz_degerlendirme_tests(brain, collector: TestOutputCollector, count: int = 8):
    """Öz Değerlendirme — her birim için rapor üretimi."""
    scenarios = [
        ("Fen", None),
        ("Fen", "2024"),
        ("IIBF", None),
        ("IIBF", "2025"),
        ("ITBF", None),
        ("ITBF", "2024"),
        ("Mimarlik", None),
        ("Mimarlik", "2025"),
    ]

    for i, (birim, yil) in enumerate(scenarios[:count]):
        suffix = f" {yil}" if yil else " (tüm yıllar)"
        test_name = f"OD-{i+1}: {birim}{suffix}"
        print(f"  ⏳ {test_name}")
        start = time.time()
        try:
            result = brain.generate_self_evaluation(birim, yil=yil)
            duration = time.time() - start
            collector.add("Öz Değerlendirme Raporu", test_name, result, duration)
            print(f"  ✅ {test_name} ({duration:.1f}s)")
        except Exception as e:
            collector.add("Öz Değerlendirme Raporu", test_name, "", time.time() - start, str(e))
            print(f"  ❌ {test_name} — Hata: {e}")


def run_rubrik_tests(brain, collector: TestOutputCollector, count: int = 8):
    """Rubrik Notlandırma — rapor bazlı rubrik analizi."""
    reports = get_available_reports()
    oz_reports = [r for r in reports if "Oz_Degerlendirme" in r or "OZ" in r.upper()]
    if not oz_reports:
        oz_reports = reports[:count]

    random.shuffle(oz_reports)
    selected = oz_reports[:count]

    for i, filename in enumerate(selected):
        test_name = f"RN-{i+1}: {filename}"
        print(f"  ⏳ {test_name}")
        start = time.time()
        try:
            result = brain.evaluate_rubric([filename])
            duration = time.time() - start
            collector.add("Rubrik Notlandırma", test_name, result, duration)
            print(f"  ✅ {test_name} ({duration:.1f}s)")
        except Exception as e:
            collector.add("Rubrik Notlandırma", test_name, "", time.time() - start, str(e))
            print(f"  ❌ {test_name} — Hata: {e}")


def run_tutarsizlik_tests(brain, collector: TestOutputCollector, count: int = 10):
    """Tutarsızlık Analizi — mock veri üretimi + doğrulama."""
    reports = get_available_reports()
    random.shuffle(reports)
    selected = reports[:count]
    modes = ["Tutarsız", "Tutarlı", "Karmaşık"]

    for i, filename in enumerate(selected):
        mode = modes[i % len(modes)]
        test_name = f"TA-{i+1}: {filename} ({mode})"
        print(f"  ⏳ {test_name}")
        start = time.time()
        try:
            # 1. Mock veri üret
            mock_data = brain.generate_mock_data(filename, mode=mode)

            # 2. Bölümleri ayır
            survey_text = ""
            comparison_text = mock_data
            if "BOLUM 2" in mock_data:
                parts = mock_data.split("BOLUM 2")
                survey_text = parts[0].strip()
                comparison_text = parts[1].strip() if len(parts) > 1 else mock_data

            # 3. Tutarsızlık analizi
            consistency_result = ""
            if comparison_text.strip():
                consistency_result = brain.check_consistency(
                    comparison_text=comparison_text,
                    survey_text=survey_text if survey_text.strip() else None,
                    filename=filename,
                )

            duration = time.time() - start

            # Çıktıyı birleştir
            combined_output = (
                f"#### 📋 Üretilen Mock Veri (Mod: {mode})\n\n"
                f"{mock_data}\n\n"
                f"---\n\n"
                f"#### 🔍 Tutarsızlık Analizi Sonucu\n\n"
                f"{consistency_result}\n"
            )
            collector.add("Tutarsızlık Analizi", test_name, combined_output, duration)
            print(f"  ✅ {test_name} ({duration:.1f}s)")
        except Exception as e:
            collector.add("Tutarsızlık Analizi", test_name, "", time.time() - start, str(e))
            print(f"  ❌ {test_name} — Hata: {e}")


# ── Ana Çalıştırma ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ReportLens Kapsamlı Sistem Testi")
    parser.add_argument("--module", type=str, default="all",
                        choices=["all", "kalite", "rapor", "oz", "rubrik", "tutarsizlik"],
                        help="Test edilecek modül")
    parser.add_argument("--count", type=int, default=None,
                        help="Her modüldeki test sayısı")
    args = parser.parse_args()

    print("\n🚀 ReportLens Kapsamlı Sistem Testi Başlatılıyor...")
    print(f"   Modül: {args.module}")
    print(f"   Zaman: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Brain başlat
    from core.brain import QualityBrain
    brain = QualityBrain()
    collector = TestOutputCollector()

    if args.module in ("all", "kalite"):
        print("\n📊 Modül 1: Kalite Analiz Uzmanı")
        print("-" * 50)
        run_kalite_tests(brain, collector, count=args.count or 10)

    if args.module in ("all", "rapor"):
        print("\n📄 Modül 2: Rapor Analizi")
        print("-" * 50)
        run_rapor_tests(brain, collector, count=args.count or 15)

    if args.module in ("all", "oz"):
        print("\n📋 Modül 3: Öz Değerlendirme Raporu")
        print("-" * 50)
        run_oz_degerlendirme_tests(brain, collector, count=args.count or 8)

    if args.module in ("all", "rubrik"):
        print("\n⚖️ Modül 4: Rubrik Notlandırma")
        print("-" * 50)
        run_rubrik_tests(brain, collector, count=args.count or 8)

    if args.module in ("all", "tutarsizlik"):
        print("\n🔍 Modül 5: Tutarsızlık Analizi")
        print("-" * 50)
        run_tutarsizlik_tests(brain, collector, count=args.count or 10)

    # Kaydet
    saved_path = collector.save()

    print("\n" + "=" * 60)
    print(f"✅ TEST TAMAMLANDI")
    print(f"   Toplam: {collector.summary['total']} test")
    print(f"   Başarılı: {collector.summary['success']}")
    print(f"   Hata: {collector.summary['error']}")
    print(f"   📁 Rapor: {saved_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
