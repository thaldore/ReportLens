// ══════════════════════════════════════════════════════════════════
// ReportLens LLM Microservice — LlmController (Tam İmplementasyon)
//
// Python'daki api/main.py endpoint'lerinin .NET LLM mikroservis karşılığı.
// Backend (port 8001) bu servisi (port 8002) dahili olarak çağırır.
//
// Dışa açık endpoint'ler:
//   POST /api/llm/analyze           ← analyze()
//   POST /api/llm/analyze-report    ← analyze_single_report()
//   POST /api/llm/self-evaluation   ← generate_self_evaluation()
//   POST /api/llm/rubric            ← evaluate_rubric()
//   POST /api/llm/consistency       ← check_consistency()
//   POST /api/llm/mock-data         ← generate_mock_data()
//   POST /api/llm/index             ← index_documents()
//   GET  /api/llm/status            ← get_status()
//   GET  /api/llm/health            ← health check
// ══════════════════════════════════════════════════════════════════

using Microsoft.AspNetCore.Mvc;
using ReportLens.LLM.Brain;
using ReportLens.LLM.VectorSearch;

namespace ReportLens.LLM.Controllers;

/// <summary>
/// LLM Mikroservis Controller'ı.
/// QualityBrain'i kullanarak Python main.py endpoint'lerine eşdeğer
/// servis sağlar. Backend bu controller'a HTTP çağrısı yapar.
/// </summary>
[ApiController]
[Route("api/llm")]
[Produces("application/json")]
public class LlmController : ControllerBase
{
    private readonly QualityBrain _brain;
    private readonly VectorStore _vectorStore;
    private readonly IConfiguration _config;
    private readonly ILogger<LlmController> _logger;

    public LlmController(
        QualityBrain brain,
        VectorStore vectorStore,
        IConfiguration config,
        ILogger<LlmController> logger)
    {
        _brain = brain;
        _vectorStore = vectorStore;
        _config = config;
        _logger = logger;
    }

    // ── Status ────────────────────────────────────────────────────

    /// <summary>GET /api/llm/health — Servis sağlık kontrolü</summary>
    [HttpGet("health")]
    public IActionResult Health()
    {
        return Ok(new
        {
            status = "healthy",
            service = "ReportLens LLM Microservice",
            framework = "ASP.NET Core 9 + Microsoft Semantic Kernel",
            version = "2.0.0"
        });
    }

    /// <summary>GET /api/llm/status — Python /api/status karşılığı</summary>
    [HttpGet("status")]
    public async Task<IActionResult> GetStatus()
    {
        try
        {
            var dbInfo = await _vectorStore.GetCollectionInfoAsync();
            var dataPath = GetDataPath();

            return Ok(new
            {
                durum = dbInfo["durum"],
                vektor_sayisi = dbInfo["toplam_nokta"],
                toplam_nokta = dbInfo["toplam_nokta"],
                tablo_adi = _config["VectorSearch:TableName"] ?? "MAF_DocumentVectors",
                model = _config["Ollama:ModelId"] ?? "llama3.1:8b",
                embedding_model = _config["Ollama:EmbeddingModel"] ?? "nomic-embed-text",
                ollama_url = _config["Ollama:BaseUrl"] ?? "—",
                mssql_db = "ReportLensDB",
                ortam = "Microsoft Agent Framework",
                framework = "ASP.NET Core 9.0 + Semantic Kernel",
                mimari = "Clean Architecture + Modular Monolith"
            });
        }
        catch (Exception ex)
        {
            return Ok(new { error = ex.Message });
        }
    }

    // ── Analiz Endpoint'leri ──────────────────────────────────────

    /// <summary>POST /api/llm/analyze — Genel kalite analizi</summary>
    [HttpPost("analyze")]
    public async Task<IActionResult> Analyze([FromBody] AnalyzeRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Query))
            return BadRequest(new { detail = "Query boş olamaz." });

        try
        {
            var (result, autoBirim, autoYil) = await _brain.AnalyzeAsync(
                request.Query, request.Birim, request.Yil);
            return Ok(new { result, auto_birim = autoBirim, auto_yil = autoYil });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Analiz hatası");
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    /// <summary>POST /api/llm/analyze-report — Tek rapor detaylı analizi</summary>
    [HttpPost("analyze-report")]
    public async Task<IActionResult> AnalyzeReport([FromBody] FilenameRequest request)
    {
        try
        {
            var result = await _brain.AnalyzeReportAsync(request.Filename);
            return Ok(new { result });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    /// <summary>POST /api/llm/self-evaluation — Öz değerlendirme raporu üretimi</summary>
    [HttpPost("self-evaluation")]
    public async Task<IActionResult> SelfEvaluation([FromBody] SelfEvalRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Birim))
            return BadRequest(new { detail = "Birim boş olamaz." });

        try
        {
            var result = await _brain.GenerateSelfEvaluationAsync(request.Birim, request.Yil);
            return Ok(new { result });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    /// <summary>POST /api/llm/rubric — YÖKAK rubrik değerlendirmesi (İki Aşamalı)</summary>
    [HttpPost("rubric")]
    public async Task<IActionResult> RubricEvaluation([FromBody] RubricRequest request)
    {
        if (!request.Filenames.Any())
            return BadRequest(new { detail = "En az bir dosya seçilmeli." });

        try
        {
            var result = await _brain.EvaluateRubricAsync(request.Filenames);
            return Ok(new { result });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    /// <summary>POST /api/llm/consistency — Tutarsızlık analizi</summary>
    [HttpPost("consistency")]
    public async Task<IActionResult> ConsistencyCheck([FromBody] ConsistencyRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.ComparisonText))
            return BadRequest(new { detail = "ComparisonText boş olamaz." });

        try
        {
            var result = await _brain.CheckConsistencyAsync(
                request.ComparisonText, request.SurveyText, request.Birim, request.Filename);
            return Ok(new { result });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    /// <summary>POST /api/llm/mock-data — Sentetik test verisi üretimi</summary>
    [HttpPost("mock-data")]
    public async Task<IActionResult> GenerateMock([FromBody] MockDataRequest request)
    {
        try
        {
            var result = await _brain.GenerateMockDataAsync(request.Filename, request.Mode);
            return Ok(new { result });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    // ── İndeksleme ────────────────────────────────────────────────

    /// <summary>POST /api/llm/index — MAF_DocumentVectors'a indeksleme</summary>
    [HttpPost("index")]
    public async Task<IActionResult> IndexDocuments([FromQuery] bool force_reindex = false)
    {
        try
        {
            var dataPath = GetDataPath();
            var indexed = await _vectorStore.IndexDocumentsAsync(dataPath, force_reindex);
            return Ok(new { indexed_chunks = indexed, message = $"{indexed} chunk MAF_DocumentVectors'a eklendi." });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    // ── Yardımcı ─────────────────────────────────────────────────

    private static string GetDataPath()
    {
        var inContainer = Environment.GetEnvironmentVariable("DOTNET_RUNNING_IN_CONTAINER") == "true";
        return inContainer
            ? "/app/Data"
            : Path.GetFullPath(Path.Combine(AppContext.BaseDirectory,
                "..", "..", "..", "..", "..", "..", "ReportLens-Python", "Data"));
    }
}

// ── Request DTOs ──────────────────────────────────────────────────

public record AnalyzeRequest(string Query, string? Birim = null, string? Yil = null);
public record FilenameRequest(string Filename);
public record SelfEvalRequest(string Birim, string? Yil = null);
public record RubricRequest(List<string> Filenames);
public record ConsistencyRequest(string ComparisonText, string? SurveyText = null, string? Birim = null, string? Filename = null);
public record MockDataRequest(string Filename, string Mode = "Tutarsız");
