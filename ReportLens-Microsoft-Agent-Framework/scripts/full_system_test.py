#!/usr/bin/env python3
"""
ReportLens Tam Sistem Testi (Python + MAF Microservices)
======================================================
Bu script hem Python hem de Microsoft Agent Framework (MAF)
ortamlarını test eder. İstatistikleri ve bağlantıları doğrular.

Kullanım:
    python scripts/full_system_test.py
"""

import requests
import json
import sys
import time
from datetime import datetime

PYTHON_BASE = "http://localhost:8000"
MAF_BACKEND = "http://localhost:8001"
MAF_LLM     = "http://localhost:8002"
TIMEOUT     = 120

GREEN = "\033[92m"
RED   = "\033[91m"
YELLOW= "\033[93m"
CYAN  = "\033[96m"
RESET = "\033[0m"
BOLD  = "\033[1m"

passed = 0
failed = 0
warnings = 0

def ok(msg):
    global passed
    passed += 1
    print(f"  {GREEN}✓ PASSED{RESET}  {msg}")

def fail(msg, detail=""):
    global failed
    failed += 1
    print(f"  {RED}✗ FAILED{RESET}  {msg}")
    if detail:
        print(f"           {detail}")

def warn(msg):
    global warnings
    warnings += 1
    print(f"  {YELLOW}⚠ WARN{RESET}    {msg}")

def info(msg):
    print(f"  {CYAN}ℹ INFO{RESET}    {msg}")

def section(title):
    print(f"\n{BOLD}{CYAN}{'═'*60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'═'*60}{RESET}")

# ── 1. Bağlantı Testleri ─────────────────────────────────────────

section("1. Sistem Bağlantı Testleri")

services = [
    ("Python Environment", PYTHON_BASE + "/api/status"),
    ("MAF Main Backend", MAF_BACKEND + "/health"),
    ("MAF LLM Microservice", MAF_LLM + "/health"),
    ("DB Adminer", "http://localhost:8080"),
    ("Ollama API", "http://localhost:11434"),
]

for name, url in services:
    try:
        r = requests.get(url, timeout=5)
        if r.status_code < 400:
            ok(f"{name} aktif ({url})")
        else:
            fail(f"{name} hata kodu döndürdü: {r.status_code}")
    except Exception as e:
        fail(f"{name} erişilemiyor: {url}")

# ── 2. Python Environment Detayları ──────────────────────────────

section("2. Python Environment (Port 8000)")

try:
    r = requests.get(f"{PYTHON_BASE}/api/status", timeout=10)
    if r.status_code == 200:
        data = r.json()
        ok("Python API durumu başarılı")
        info(f"Vektör Sayısı: {data.get('toplam_nokta', 0)}")
        info(f"Tablo: {data.get('tablo_adi', 'Python_DocumentVectors')}")
    else:
        fail(f"Python Status HTTP {r.status_code}")
except Exception as e:
    fail("Python status hatası", str(e))

# ── 3. MAF Environment Detayları ─────────────────────────────────

section("3. Microsoft Agent Framework (Ports 8001/8002)")

try:
    # Backend üzerinden status al (LLM servisine proxy yapar)
    r = requests.get(f"{MAF_BACKEND}/api/status", timeout=15)
    if r.status_code == 200:
        data = r.json()
        ok("MAF Status (Proxy üzerinden) başarılı")
        info(f"Framework: {data.get('framework', '?')}")
        info(f"Vektör Sayısı: {data.get('vektor_sayisi', 0)}")
        info(f"Tablo: {data.get('tablo_adi', 'MAF_DocumentVectors')}")
        info(f"Oturum: {data.get('ortam', '?')}")
    else:
        fail(f"MAF Status HTTP {r.status_code}")
except Exception as e:
    fail("MAF status hatası", str(e))

# ── 4. Raporlar ve Birimler (MAF) ────────────────────────────────

section("4. Veri Tutarlılığı Testi (MAF)")

reports = []
try:
    r = requests.get(f"{MAF_BACKEND}/api/reports", timeout=10)
    if r.status_code == 200:
        reports = r.json().get("reports", [])
        ok(f"MAF Raporları: {len(reports)} adet bulundu")
    else:
        fail(f"MAF Reports HTTP {r.status_code}")
except Exception as e:
    fail("MAF reports hatası", str(e))

# ── 5. Analiz Testi (MAF LLM Microservice) ───────────────────────

section("5. MAF LLM Analiz Testi (6 Agent Orkestrasyonu)")

if reports:
    try:
        print(f"  ⏳ Analiz yapılıyor (8001 -> 8002 -> Ollama)...")
        start = time.time()
        r = requests.post(f"{MAF_BACKEND}/api/analyze", json={
            "query": "Hangi fakültelerin kalite raporları mevcut?"
        }, timeout=TIMEOUT)
        elapsed = time.time() - start
        if r.status_code == 200:
            res = r.json()
            ok(f"Analiz başarılı ({elapsed:.1f}s)")
            info(f"Tespit edilen birim: {res.get('auto_birim', 'Yok')}")
            content = res.get("result", "")
            if len(content) > 100:
                print(f"\n{RESET}{content[:400]}...\n")
            else:
                warn("Analiz sonucu beklenenden kısa.")
        else:
            fail(f"Analiz hatası: {r.status_code}", r.text[:200])
    except Exception as e:
        fail("Analiz isteği başarısız", str(e))
else:
    warn("Rapor bulunamadığı için analiz testi atlandı.")

# ── Sonuç ────────────────────────────────────────────────────────

section("GENEL TEST ÖZETİ")

total = passed + failed
print(f"\n  {GREEN}✓ Başarılı:{RESET} {passed}/{total}")
print(f"  {RED}✗ Başarısız:{RESET} {failed}/{total}")
print(f"  {YELLOW}⚠ Uyarı:{RESET} {warnings}")
print(f"\n  Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if failed == 0:
    print(f"\n{GREEN}{BOLD}  ✅ TÜM SİSTEMLER OPERASYONEL{RESET}")
else:
    print(f"\n{RED}{BOLD}  ❌ SİSTEMDE KRİTİK HATALAR MEVCUT{RESET}")
    sys.exit(1)
