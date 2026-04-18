// ══════════════════════════════════════════════════════════════════
// ReportLens MAF Backend — WebApi: Analysis Controller
// Python api/main.py'deki tum endpoint'lerin .NET karsiligi.
// Clean Architecture: Controller sadece DTO alir, servise deleg eder.
// ══════════════════════════════════════════════════════════════════

using Microsoft.AspNetCore.Mvc;
using ReportLens.Application.DTOs;
using ReportLens.Application.Interfaces;

namespace ReportLens.WebApi.Controllers;

/// <summary>
/// Ana analiz API Controller'i.
/// Python'daki api/main.py endpoint'lerinin tam .NET karsiligi.
/// Route: /api/[controller] = /api/analysis
/// NOT: Python ile ayni URL yapisini korumak icin attribute routing kullanildi.
/// </summary>
[ApiController]
[Route("api")]
[Produces("application/json")]
public class AnalysisController : ControllerBase
{
    private readonly IAnalysisService _analysis;
    private readonly IVectorSearchService _vectorSearch;
    private readonly IDocumentProcessor _processor;
    private readonly IConfiguration _config;
    private readonly ILogger<AnalysisController> _logger;

    public AnalysisController(
        IAnalysisService analysis,
        IVectorSearchService vectorSearch,
        IDocumentProcessor processor,
        IConfiguration config,
        ILogger<AnalysisController> logger)
    {
        _analysis = analysis;
        _vectorSearch = vectorSearch;
        _processor = processor;
        _config = config;
        _logger = logger;
    }

    // ── Sistem Durumu ─────────────────────────────────────────────────

    /// <summary>GET /api/status — Python'daki /api/status karsiligi</summary>
    [HttpGet("status")]
    public async Task<IActionResult> GetStatus()
    {
        try
        {
            var status = await _analysis.GetStatusAsync();
            return Ok(status);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Status alinamadi");
            return Ok(new { error = ex.Message });
        }
    }

    /// <summary>GET /api/birimler — Mevcut birimleri listeler</summary>
    [HttpGet("birimler")]
    public IActionResult GetBirimler()
    {
        var birimler = _processor.GetProcessedFiles()
            .Select(f => f.Split('_').FirstOrDefault() ?? "")
            .Where(b => !string.IsNullOrEmpty(b))
            .Distinct()
            .OrderBy(b => b)
            .ToList();

        return Ok(new { birimler });
    }

    /// <summary>GET /api/reports — Islenmiş raporları listeler</summary>
    [HttpGet("reports")]
    public IActionResult GetReports()
    {
        var dataPath = GetDataPath();
        var processedDir = Path.Combine(dataPath, "processed");
        var reports = new List<object>();

        if (Directory.Exists(processedDir))
        {
            foreach (var f in Directory.GetFiles(processedDir, "*.md").OrderBy(f => f))
            {
                var stem = Path.GetFileNameWithoutExtension(f);
                var parts = stem.Split('_');
                reports.Add(new
                {
                    filename = Path.GetFileName(f),
                    birim = parts.Length > 0 ? parts[0] : "-",
                    yil = parts.Length > 1 && parts[1].All(char.IsDigit) ? parts[1] : "-",
                    tur = parts.Length > 2 ? string.Join(" ", parts[2..]) : "-",
                    size_kb = Math.Round(new FileInfo(f).Length / 1024.0, 1)
                });
            }
        }

        return Ok(new { reports });
    }

    /// <summary>GET /api/raw-files — Ham dosyaları listeler</summary>
    [HttpGet("raw-files")]
    public IActionResult GetRawFiles()
    {
        var dataPath = GetDataPath();
        var rawDir = Path.Combine(dataPath, "raw_data");
        var extensions = new[] { ".pdf", ".docx", ".xlsx", ".xls", ".csv" };
        var files = new List<object>();

        if (Directory.Exists(rawDir))
        {
            foreach (var f in Directory.GetFiles(rawDir, "*.*", SearchOption.AllDirectories)
                .Where(f => extensions.Contains(Path.GetExtension(f).ToLowerInvariant())))
            {
                var stem = Path.GetFileNameWithoutExtension(f);
                var parts = stem.Split('_');
                var processedPath = Path.Combine(dataPath, "processed", stem + ".md");
                files.Add(new
                {
                    filename = Path.GetFileName(f),
                    birim = parts.Length > 0 ? parts[0] : "-",
                    yil = parts.Length > 1 && parts[1].All(char.IsDigit) ? parts[1] : "-",
                    tur = parts.Length > 2 ? string.Join(" ", parts[2..]) : "-",
                    size_mb = Math.Round(new FileInfo(f).Length / (1024.0 * 1024), 1),
                    processed = System.IO.File.Exists(processedPath)
                });
            }
        }

        return Ok(new { files });
    }

    // ── Analiz Endpoint'leri ─────────────────────────────────────────

    /// <summary>POST /api/analyze — Genel kalite analizi</summary>
    [HttpPost("analyze")]
    public async Task<IActionResult> Analyze([FromBody] AnalyzeRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Query))
            return BadRequest(new { detail = "Query bos olamaz." });

        try
        {
            var (result, autoBirim, autoYil) = await _analysis.AnalyzeAsync(request.Query, request.Birim, request.Yil);
            return Ok(new { result, auto_birim = autoBirim, auto_yil = autoYil });
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Analiz hatasi");
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    /// <summary>POST /api/analyze-report — Belirli bir raporu analiz eder</summary>
    [HttpPost("analyze-report")]
    public async Task<IActionResult> AnalyzeReport([FromBody] SingleReportRequest request)
    {
        try
        {
            var result = await _analysis.AnalyzeReportAsync(request.Filename);
            return Ok(new { result });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    /// <summary>POST /api/self-evaluation — Oz degerlendirme raporu uretir</summary>
    [HttpPost("self-evaluation")]
    public async Task<IActionResult> SelfEvaluation([FromBody] SelfEvalRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.Birim))
            return BadRequest(new { detail = "Birim bos olamaz." });

        try
        {
            var result = await _analysis.GenerateSelfEvaluationAsync(request.Birim, request.Yil);
            return Ok(new { result });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    /// <summary>POST /api/rubric — Rubrik notlandirma</summary>
    [HttpPost("rubric")]
    public async Task<IActionResult> RubricEvaluation([FromBody] RubricRequest request)
    {
        if (!request.Filenames.Any())
            return BadRequest(new { detail = "En az bir dosya secilmeli." });

        try
        {
            var result = await _analysis.EvaluateRubricAsync(request.Filenames);
            return Ok(new { result });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    /// <summary>POST /api/consistency — Tutarsizlik analizi</summary>
    [HttpPost("consistency")]
    public async Task<IActionResult> ConsistencyCheck([FromBody] ConsistencyRequest request)
    {
        if (string.IsNullOrWhiteSpace(request.ComparisonText))
            return BadRequest(new { detail = "ComparisonText bos olamaz." });

        try
        {
            var result = await _analysis.CheckConsistencyAsync(
                request.ComparisonText, request.SurveyText, request.Birim, request.Filename);
            return Ok(new { result });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    /// <summary>POST /api/mock-data — Sahte test verisi uretir</summary>
    [HttpPost("mock-data")]
    public async Task<IActionResult> GenerateMock([FromBody] MockDataRequest request)
    {
        try
        {
            var result = await _analysis.GenerateMockDataAsync(request.Filename, request.Mode);
            return Ok(new { result });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    // ── Indeksleme ────────────────────────────────────────────────────

    /// <summary>POST /api/process — Dosyalari indeksler (PDF donusumu Python tarafinda)</summary>
    [HttpPost("process")]
    public async Task<IActionResult> ProcessAndIndex([FromQuery] bool force_reindex = false)
    {
        try
        {
            var indexed = await _vectorSearch.IndexDocumentsAsync(force_reindex);
            return Ok(new { indexed_chunks = indexed, message = "Indeksleme tamamlandi. PDF/DOCX donusumu Python API (port 8000) araciligiyla yapilir." });
        }
        catch (Exception ex)
        {
            return StatusCode(500, new { detail = ex.Message });
        }
    }

    /// <summary>GET /api/test-results — Test sonuclarini listeler</summary>
    [HttpGet("test-results")]
    public IActionResult GetTestResults()
    {
        var dataPath = GetDataPath();
        var testDir = Path.Combine(dataPath, "test_results");
        if (!Directory.Exists(testDir)) return Ok(new { results = new List<object>() });

        var results = Directory.GetFiles(testDir, "test_raporu_*.md")
            .OrderByDescending(f => f)
            .Select(f => new { filename = Path.GetFileName(f) })
            .ToList();

        return Ok(new { results });
    }

    // ── Yardimci ─────────────────────────────────────────────────────

    private static string GetDataPath()
    {
        var inContainer = Environment.GetEnvironmentVariable("DOTNET_RUNNING_IN_CONTAINER") == "true";
        return inContainer
            ? "/app/Data"
            : Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "ReportLens-Python", "Data"));
    }
}
