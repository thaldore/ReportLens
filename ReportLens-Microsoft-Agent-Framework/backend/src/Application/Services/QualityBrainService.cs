// ══════════════════════════════════════════════════════════════════
// ReportLens MAF Backend — Application Service: QualityBrainService (Proxy)
// Python'daki brain.py/QualityBrain sinifinin .NET karsiligi.
// Artik bir "Proxy" olarak calisir ve istekleri ReportLens-LLM
// mikroservisine iletir.
// ══════════════════════════════════════════════════════════════════

using ReportLens.Application.Interfaces;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Configuration;
using System.Net.Http.Json;

namespace ReportLens.Application.Services;

/// <summary>
/// Ana kalite analiz orkestratoru (Client/Proxy).
/// Tum AI islerini 'reportlens-maf-llm' mikroservisine delege eder.
/// </summary>
public class QualityBrainService : IAnalysisService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<QualityBrainService> _logger;
    private readonly string _llmBaseUrl;

    public QualityBrainService(
        IHttpClientFactory httpClientFactory,
        ILogger<QualityBrainService> logger,
        IConfiguration config)
    {
        _httpClient = httpClientFactory.CreateClient("LLM_Microservice");
        _logger = logger;
        _llmBaseUrl = config["LLM:BaseUrl"] ?? "http://localhost:8002";
    }

    public async Task<(string Result, string? AutoBirim, string? AutoYil)> AnalyzeAsync(
        string query, string? birim = null, string? yil = null)
    {
        _logger.LogInformation("AnalyzeAsync calling LLM Microservice: {Query}", query);
        var response = await _httpClient.PostAsJsonAsync($"{_llmBaseUrl}/api/llm/analyze", new { query, birim, yil });
        response.EnsureSuccessStatusCode();
        var data = await response.Content.ReadFromJsonAsync<AnalyzeResponse>();
        return (data?.Result ?? "", data?.Auto_Birim, data?.Auto_Yil);
    }

    public async Task<string> AnalyzeReportAsync(string filename)
    {
        var response = await _httpClient.PostAsJsonAsync($"{_llmBaseUrl}/api/llm/analyze-report", new { filename });
        response.EnsureSuccessStatusCode();
        var data = await response.Content.ReadFromJsonAsync<ResultResponse>();
        return data?.Result ?? "";
    }

    public async Task<string> GenerateSelfEvaluationAsync(string birim, string? yil = null)
    {
        var response = await _httpClient.PostAsJsonAsync($"{_llmBaseUrl}/api/llm/self-evaluation", new { birim, yil });
        response.EnsureSuccessStatusCode();
        var data = await response.Content.ReadFromJsonAsync<ResultResponse>();
        return data?.Result ?? "";
    }

    public async Task<string> EvaluateRubricAsync(IEnumerable<string> filenames)
    {
        var response = await _httpClient.PostAsJsonAsync($"{_llmBaseUrl}/api/llm/rubric", new { filenames = filenames.ToList() });
        response.EnsureSuccessStatusCode();
        var data = await response.Content.ReadFromJsonAsync<ResultResponse>();
        return data?.Result ?? "";
    }

    public async Task<string> CheckConsistencyAsync(string comparisonText, string? surveyText = null, string? birim = null, string? filename = null)
    {
        var response = await _httpClient.PostAsJsonAsync($"{_llmBaseUrl}/api/llm/consistency", new { comparisonText, surveyText, birim, filename });
        response.EnsureSuccessStatusCode();
        var data = await response.Content.ReadFromJsonAsync<ResultResponse>();
        return data?.Result ?? "";
    }

    public async Task<string> GenerateMockDataAsync(string filename, string mode = "Tutarsiz")
    {
        var response = await _httpClient.PostAsJsonAsync($"{_llmBaseUrl}/api/llm/mock-data", new { filename, mode });
        response.EnsureSuccessStatusCode();
        var data = await response.Content.ReadFromJsonAsync<ResultResponse>();
        return data?.Result ?? "";
    }

    public async Task<Dictionary<string, object>> GetStatusAsync()
    {
        var response = await _httpClient.GetAsync($"{_llmBaseUrl}/api/llm/status");
        if (response.IsSuccessStatusCode)
        {
            return await response.Content.ReadFromJsonAsync<Dictionary<string, object>>() ?? new();
        }
        return new Dictionary<string, object> { ["status"] = "LLM Service Offline" };
    }

    // ── Internal Helpers ──────────────────────────────────────────

    private record AnalyzeResponse(string Result, string? Auto_Birim, string? Auto_Yil);
    private record ResultResponse(string Result);
}
