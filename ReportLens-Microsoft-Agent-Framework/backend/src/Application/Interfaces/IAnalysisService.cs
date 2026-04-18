// ══════════════════════════════════════════════════════════════════
// ReportLens MAF Backend — Application Interfaces
// Clean Architecture: Port tanımları. Tüm dış bağımlılıklar bu
// interface'ler üzerinden erişilir (Dependency Inversion).
// ══════════════════════════════════════════════════════════════════

namespace ReportLens.Application.Interfaces;

/// <summary>
/// Ana analiz servisi sözleşmesi.
/// QualityBrain'in .NET karşılığı — 6 ajanlı orkestrasyon.
/// </summary>
public interface IAnalysisService
{
    Task<(string Result, string? AutoBirim, string? AutoYil)> AnalyzeAsync(string query, string? birim = null, string? yil = null);
    Task<string> AnalyzeReportAsync(string filename);
    Task<string> GenerateSelfEvaluationAsync(string birim, string? yil = null);
    Task<string> EvaluateRubricAsync(IEnumerable<string> filenames);
    Task<string> CheckConsistencyAsync(string comparisonText, string? surveyText = null, string? birim = null, string? filename = null);
    Task<string> GenerateMockDataAsync(string filename, string mode = "Tutarsız");
    Task<Dictionary<string, object>> GetStatusAsync();
}

/// <summary>
/// Vektör arama servisi sözleşmesi.
/// SQL Server 2025 native VECTOR_DISTANCE kullanır.
/// </summary>
public interface IVectorSearchService
{
    Task<string> SearchAsync(string query, int k = 15, string? birim = null, string? yil = null, string? filename = null);
    Task<int> IndexDocumentsAsync(bool forceReindex = false);
    Task<Dictionary<string, object>> GetCollectionInfoAsync();
    Task<List<Dictionary<string, object>>> GetFileContentAsync(string filename, int limit = 20);
}

/// <summary>
/// LLM (Ollama) servisi sözleşmesi.
/// Semantic Kernel ile Ollama arasındaki köprü.
/// </summary>
public interface ILlmService
{
    Task<string> GenerateAsync(string systemPrompt, string userPrompt, double temperature = 0.1);
    Task<float[]> EmbedAsync(string text);
    Task<bool> CheckConnectionAsync();
    Task<List<string>> GetLoadedModelsAsync();
}

/// <summary>
/// Döküman işleme servisi sözleşmesi.
/// PDF/DOCX → Markdown dönüşümü.
/// </summary>
public interface IDocumentProcessor
{
    Task<int> ConvertFilesAsync();
    IEnumerable<string> GetProcessedFiles();
    IEnumerable<string> GetRawFiles();
    int GetRawFileCount();
    int GetProcessedFileCount();
}
