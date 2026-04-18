// ══════════════════════════════════════════════════════════════════
// ReportLens MAF Backend — Infrastructure: Document Processor
// Islenmis markdown dosyalarini okur.
// Python'daki processor.py'nin .NET (salt okunur) karsiligi.
// NOT: PDF/DOCX donusumu Python tarafinda yapilmaktadir.
//      Bu servis sadece /app/Data/processed/ dizininden okur.
// ══════════════════════════════════════════════════════════════════

using ReportLens.Application.Interfaces;

namespace ReportLens.Infrastructure.Processing;

/// <summary>
/// Islenmis markdown dosyalarini listeleyen belge isleyici.
/// Python'daki ReportProcessor'ın .NET readonly karsiligi.
/// PDF/DOCX donusum Python tarafinda gerceklesiyor; bu servis
/// paylasilan Data/processed/ dizininden okur (volume bağlantısı).
/// </summary>
public class DocumentProcessor : IDocumentProcessor
{
    private readonly string _rawDataPath;
    private readonly string _processedDataPath;
    private readonly ILogger<DocumentProcessor> _logger;

    public DocumentProcessor(IConfiguration configuration, ILogger<DocumentProcessor> logger)
    {
        var dataRoot = GetDataPath();
        _rawDataPath = Path.Combine(dataRoot, "raw_data");
        _processedDataPath = Path.Combine(dataRoot, "processed");
        _logger = logger;
    }

    public Task<int> ConvertFilesAsync()
    {
        // .NET tarafinda PDF donusumu yapilmiyor.
        // Bu metod Python servisine yonlendirme mesaji verir.
        _logger.LogInformation("PDF/DOCX donusumu icin Python API'sini (port 8000) kullanin.");
        return Task.FromResult(0);
    }

    public IEnumerable<string> GetProcessedFiles()
    {
        if (!Directory.Exists(_processedDataPath)) return [];
        return Directory.GetFiles(_processedDataPath, "*.md")
            .Select(Path.GetFileName)
            .Where(f => f != null)
            .Cast<string>();
    }

    public IEnumerable<string> GetRawFiles()
    {
        if (!Directory.Exists(_rawDataPath)) return [];
        return Directory.GetFiles(_rawDataPath, "*.*", SearchOption.AllDirectories)
            .Where(f => new[] { ".pdf", ".docx", ".xlsx", ".xls", ".csv" }
                .Contains(Path.GetExtension(f).ToLowerInvariant()))
            .Select(Path.GetFileName)
            .Where(f => f != null)
            .Cast<string>();
    }

    public int GetRawFileCount()
    {
        if (!Directory.Exists(_rawDataPath)) return 0;
        return Directory.GetFiles(_rawDataPath, "*.*", SearchOption.AllDirectories)
            .Count(f => new[] { ".pdf", ".docx", ".xlsx", ".xls", ".csv" }
                .Contains(Path.GetExtension(f).ToLowerInvariant()));
    }

    public int GetProcessedFileCount()
    {
        if (!Directory.Exists(_processedDataPath)) return 0;
        return Directory.GetFiles(_processedDataPath, "*.md").Length;
    }

    public string GetProcessedContent(string filename)
    {
        var filePath = Path.Combine(_processedDataPath, filename);
        if (!File.Exists(filePath)) return string.Empty;
        return File.ReadAllText(filePath);
    }

    private static string GetDataPath()
    {
        var inContainer = Environment.GetEnvironmentVariable("DOTNET_RUNNING_IN_CONTAINER") == "true";
        return inContainer
            ? "/app/Data"
            : Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", "..", "..", "ReportLens-Python", "Data"));
    }
}
