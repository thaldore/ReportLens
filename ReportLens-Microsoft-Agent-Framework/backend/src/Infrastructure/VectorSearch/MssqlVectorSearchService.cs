// ══════════════════════════════════════════════════════════════════
// ReportLens MAF Backend — Infrastructure: MSSQL Vector Search (Proxy)
// Artik bir "Proxy" olarak calisir ve vektor islerini ReportLens-LLM
// mikroservisine delege eder.
// ══════════════════════════════════════════════════════════════════

using ReportLens.Application.Interfaces;
using System.Net.Http.Json;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Configuration;

namespace ReportLens.Infrastructure.VectorSearch;

/// <summary>
/// Vektor arama ve indeksleme islerini 'reportlens-maf-llm' servisine yonlendiren proxy.
/// </summary>
public class MssqlVectorSearchService : IVectorSearchService
{
    private readonly HttpClient _httpClient;
    private readonly ILogger<MssqlVectorSearchService> _logger;
    private readonly string _llmBaseUrl;

    public MssqlVectorSearchService(
        IHttpClientFactory httpClientFactory,
        ILogger<MssqlVectorSearchService> logger,
        IConfiguration config)
    {
        _httpClient = httpClientFactory.CreateClient("LLM_Microservice");
        _logger = logger;
        _llmBaseUrl = config["LLM:BaseUrl"] ?? "http://localhost:8002";
    }

    public async Task EnsureTableExistsAsync()
    {
        // LLM servisi baslarken zaten tabloyu kontrol ediyor.
        _logger.LogInformation("EnsureTableExistsAsync: Delege edilen servis tarafından yonetiliyor.");
        await Task.CompletedTask;
    }

    public async Task<string> SearchAsync(string query, int k = 15, string? birim = null, string? yil = null, string? filename = null)
    {
        // Arama islemi artik QualityBrainService (Proxy) uzerinden QualityBrain (LLM) tarafindan yapiliyor.
        // IVectorSearchService.SearchAsync dogrudan cagrilirsa LLM servisine yonlendirilebilir.
        // Ancak mimari geregi QualityBrainService ana giris noktasidir.
        _logger.LogDebug("SearchAsync delege ediliyor...");
        return ""; // QualityBrainService zaten LLM uzerinden search yapiyor.
    }

    public async Task<int> IndexDocumentsAsync(bool forceReindex = false)
    {
        _logger.LogInformation("Indeksleme baslatiliyor (LLM Microservice uzerinden)...");
        var response = await _httpClient.PostAsync($"{_llmBaseUrl}/api/llm/index?force_reindex={forceReindex}", null);
        response.EnsureSuccessStatusCode();
        var data = await response.Content.ReadFromJsonAsync<IndexResponse>();
        return data?.Indexed_Chunks ?? 0;
    }

    public async Task<Dictionary<string, object>> GetCollectionInfoAsync()
    {
        var response = await _httpClient.GetAsync($"{_llmBaseUrl}/api/llm/status");
        if (response.IsSuccessStatusCode)
        {
            return await response.Content.ReadFromJsonAsync<Dictionary<string, object>>() ?? new();
        }
        return new Dictionary<string, object> { ["status"] = "LLM Service Offline" };
    }

    public async Task<List<Dictionary<string, object>>> GetFileContentAsync(string filename, int limit = 20)
    {
        // Bu metod LLM servisinde henuz endpoint olarak yok, istenirse eklenebilir.
        // Simdilik bos donuyoruz.
        return new List<Dictionary<string, object>>();
    }

    private record IndexResponse(int Indexed_Chunks);
}
