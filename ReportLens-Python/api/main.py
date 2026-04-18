"""
ReportLens FastAPI Backend.
Tüm analiz, rapor yönetimi ve sistem durumu endpoint'lerini sağlar.
Streamlit yerine statik HTML/CSS/JS frontend ile iletişim kurar.
"""
import os
import sys
import json
from pathlib import Path
from typing import Optional, List

# Proje kökünü Python yoluna ekle
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from core.brain import QualityBrain
from core.config import Config
from core.logging_config import get_logger

logger = get_logger(__name__)

# ── Pydantic Modelleri ──────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    query: str
    birim: Optional[str] = None
    yil: Optional[str] = None

class SingleReportRequest(BaseModel):
    filename: str

class SelfEvalRequest(BaseModel):
    birim: str
    yil: Optional[str] = None

class RubricRequest(BaseModel):
    filenames: List[str]

class ConsistencyRequest(BaseModel):
    comparison_text: str
    survey_text: Optional[str] = None
    birim: Optional[str] = None
    filename: Optional[str] = None

class MockDataRequest(BaseModel):
    filename: str
    mode: str = "Tutarsız"

# ── FastAPI Uygulama ────────────────────────────────────────────────

app = FastAPI(
    title="ReportLens API",
    description="Üniversite Kalite Raporu Analiz Sistemi REST API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Statik frontend dosyalarını sun
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

# ── Brain Singleton ─────────────────────────────────────────────────

_brain: Optional[QualityBrain] = None

def get_brain() -> QualityBrain:
    global _brain
    if _brain is None:
        try:
            _brain = QualityBrain()
        except Exception as e:
            logger.error(f"QualityBrain başlatılamadı: {e}")
            raise HTTPException(status_code=503, detail=f"Sistem başlatılamadı: {str(e)}")
    return _brain

# ── Root & Frontend ─────────────────────────────────────────────────

@app.get("/")
async def root():
    """Ana sayfa — frontend index.html"""
    index_file = frontend_dir / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "ReportLens API v2.0.0", "status": "active"}

# ── Sistem Durumu ───────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    """Sistem durumu bilgisi döner."""
    try:
        brain = get_brain()
        return brain.get_status()
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/birimler")
async def get_birimler():
    """Mevcut birimleri listeler."""
    birimler = set()
    for f in Config.PROCESSED_DATA_DIR.glob("*.md"):
        parts = f.stem.split("_")
        if parts:
            birimler.add(parts[0])
    return {"birimler": sorted(list(birimler))}

@app.get("/api/reports")
async def get_reports():
    """İşlenmiş raporları listeler."""
    reports = []
    for f in sorted(Config.PROCESSED_DATA_DIR.glob("*.md")):
        parts = f.stem.split("_")
        birim = parts[0] if parts else "-"
        yil = parts[1] if len(parts) >= 2 and parts[1].isdigit() else "-"
        tur = " ".join(parts[2:]) if len(parts) >= 3 else "-"
        reports.append({
            "filename": f.name,
            "birim": birim,
            "yil": yil,
            "tur": tur,
            "size_kb": round(f.stat().st_size / 1024, 1),
        })
    return {"reports": reports}

@app.get("/api/raw-files")
async def get_raw_files():
    """Ham dosyaları listeler."""
    files = []
    if Config.RAW_DATA_DIR.exists():
        for f in sorted(Config.RAW_DATA_DIR.glob("**/*")):
            if f.suffix.lower() in [".pdf", ".docx", ".xlsx", ".xls", ".csv"]:
                parts = f.stem.split("_")
                processed = (Config.PROCESSED_DATA_DIR / f"{f.stem}.md").exists()
                files.append({
                    "filename": f.name,
                    "birim": parts[0] if parts else "-",
                    "yil": parts[1] if len(parts) >= 2 and parts[1].isdigit() else "-",
                    "tur": " ".join(parts[2:]) if len(parts) >= 3 else "-",
                    "size_mb": round(f.stat().st_size / (1024 * 1024), 1),
                    "processed": processed,
                })
    return {"files": files}

# ── Analiz Endpoint'leri ────────────────────────────────────────────

@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    """Genel kalite analizi."""
    brain = get_brain()
    try:
        result = brain.analyze(req.query, birim=req.birim, yil=req.yil)
        if isinstance(result, tuple):
            response, auto_birim, auto_yil = result
            return {
                "result": response,
                "auto_birim": auto_birim,
                "auto_yil": auto_yil,
            }
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analyze-report")
async def analyze_report(req: SingleReportRequest):
    """Belirli bir raporu analiz eder."""
    brain = get_brain()
    try:
        result = brain.analyze_single_report(req.filename)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/self-evaluation")
async def self_evaluation(req: SelfEvalRequest):
    """Öz değerlendirme raporu üretir."""
    brain = get_brain()
    try:
        result = brain.generate_self_evaluation(req.birim, yil=req.yil)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/rubric")
async def rubric_evaluation(req: RubricRequest):
    """Rubrik notlandırma yapar."""
    brain = get_brain()
    try:
        result = brain.evaluate_rubric(req.filenames)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/consistency")
async def consistency_check(req: ConsistencyRequest):
    """Tutarsızlık analizi yapar."""
    brain = get_brain()
    try:
        result = brain.check_consistency(
            comparison_text=req.comparison_text,
            survey_text=req.survey_text,
            filename=req.filename,
            birim=req.birim,
        )
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/mock-data")
async def generate_mock(req: MockDataRequest):
    """Sahte test verisi üretir."""
    brain = get_brain()
    try:
        result = brain.generate_mock_data(req.filename, mode=req.mode)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Dosya Yönetimi ──────────────────────────────────────────────────

@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    """Rapor dosyaları yükler."""
    Config.ensure_directories()
    uploaded = []
    for file in files:
        save_path = Config.RAW_DATA_DIR / file.filename
        with open(save_path, "wb") as f:
            content = await file.read()
            f.write(content)
        uploaded.append(file.filename)
    return {"uploaded": uploaded, "count": len(uploaded)}

@app.post("/api/process")
async def process_and_index(force_reindex: bool = False):
    """Dosyaları işler ve indeksler."""
    brain = get_brain()
    try:
        result = brain.process_and_index(force_reindex=force_reindex)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reprocess-empty")
async def reprocess_empty():
    """Boş dosyaları yeniden işler."""
    brain = get_brain()
    try:
        result = brain.reprocess_empty_files()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/empty-files")
async def get_empty_files():
    """Boş işlenmiş dosyaları listeler."""
    brain = get_brain()
    empty = brain.processor.check_empty_processed_files()
    return {"files": [
        {"filename": e["md_file"].name, "size": e["size"], "has_raw": e["raw_file"] is not None}
        for e in empty
    ]}

# ── Test Sonuçları ──────────────────────────────────────────────────

@app.get("/api/test-results")
async def get_test_results():
    """Test sonuçlarını listeler."""
    results = []
    if Config.TEST_RESULTS_DIR.exists():
        for f in sorted(Config.TEST_RESULTS_DIR.glob("test_raporu_*.md"), reverse=True):
            json_name = f.name.replace("test_raporu_", "test_results_").replace(".md", ".json")
            json_path = Config.TEST_RESULTS_DIR / json_name
            meta = {}
            if json_path.exists():
                try:
                    meta = json.loads(json_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            results.append({
                "filename": f.name,
                "meta": meta,
            })
    return {"results": results}

@app.get("/api/test-results/{filename}")
async def get_test_result_content(filename: str):
    """Belirli bir test raporunun içeriğini döner."""
    path = Config.TEST_RESULTS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Test raporu bulunamadı")
    content = path.read_text(encoding="utf-8")
    return {"content": content}

# ── Uygulama Çalıştırma ────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
