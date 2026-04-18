// ══════════════════════════════════════════════════════════════════
// ReportLens LLM Microservice — VectorStore
//
// Python'daki core/vector_store.py'nin .NET karşılığı.
// SQL Server 2025 native VECTOR_DISTANCE ile semantik arama.
// Tablo: MAF_DocumentVectors (environment prefixli)
// ══════════════════════════════════════════════════════════════════

using Microsoft.Data.SqlClient;
using System.Text;
using System.Text.Json;
using Microsoft.SemanticKernel;

namespace ReportLens.LLM.VectorSearch;

/// <summary>
/// SQL Server 2025 native VECTOR araması.
/// Python'daki VectorStore sınıfının .NET karşılığı.
///
/// Python:
///   store = VectorStore(config)
///   results = store.search(query, k=15, birim="Fen")
///
/// .NET:
///   var store = new VectorStore(connStr, ollamaUrl, model);
///   var results = await store.SearchAsync(query, k: 15, birim: "Fen");
/// </summary>
public class VectorStore
{
    private readonly string _connectionString;
    private readonly string _tableName;
    private readonly string _ollamaBaseUrl;
    private readonly string _embeddingModel;
    private readonly HttpClient _httpClient;
    private readonly ILogger<VectorStore> _logger;
    private const int VectorDimension = 768;  // nomic-embed-text

    public VectorStore(
        IConfiguration configuration,
        IHttpClientFactory httpClientFactory,
        ILogger<VectorStore> logger)
    {
        _connectionString = configuration.GetConnectionString("VectorDb")
            ?? throw new InvalidOperationException("VectorDb connection string bulunamadı.");
        _tableName = configuration["VectorSearch:TableName"] ?? "MAF_DocumentVectors";
        _ollamaBaseUrl = configuration["Ollama:BaseUrl"] ?? "http://reportlens-ollama:11434";
        _embeddingModel = configuration["Ollama:EmbeddingModel"] ?? "nomic-embed-text";
        _httpClient = httpClientFactory.CreateClient("ollama");
        _logger = logger;
    }

    /// <summary>
    /// Tablo oluşturur (yoksa). Python'daki _create_table() karşılığı.
    /// </summary>
    public async Task EnsureTableExistsAsync()
    {
        var sql = $@"
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='{_tableName}' AND xtype='U')
            BEGIN
                CREATE TABLE {_tableName} (
                    Id           INT IDENTITY(1,1) PRIMARY KEY,
                    FileName     NVARCHAR(500)      NOT NULL,
                    Birim        NVARCHAR(100)      NULL,
                    Yil          NVARCHAR(10)       NULL,
                    Tur          NVARCHAR(200)      NULL,
                    BolumBasligi NVARCHAR(500)      NULL,
                    Content      NVARCHAR(MAX)      NOT NULL,
                    ContentHash  NVARCHAR(64)       NULL,
                    Vector       VECTOR({VectorDimension}) NULL,
                    IndexedAt    DATETIME2          DEFAULT GETUTCDATE()
                );
            END";

        using var conn = new SqlConnection(_connectionString);
        await conn.OpenAsync();
        using var cmd = new SqlCommand(sql, conn);
        await cmd.ExecuteNonQueryAsync();
        _logger.LogInformation("Tablo hazır: {Table}", _tableName);
    }

    /// <summary>
    /// Semantik vektör araması.
    /// Python'daki VectorStore.search() metodunun .NET karşılığı.
    ///
    /// Python:
    ///   results = self.vector_store.search(query, k=15, birim=birim, yil=yil)
    ///
    /// .NET:
    ///   var results = await _vectorStore.SearchAsync(query, k: 15, birim: birim, yil: yil);
    /// </summary>
    public async Task<string> SearchAsync(
        string query, int k = 15,
        string? birim = null, string? yil = null, string? filename = null)
    {
        try
        {
            float[]? queryVector = null;
            if (!string.IsNullOrWhiteSpace(query))
                queryVector = await EmbedAsync(query);

            var whereClause = "1=1";
            var parameters = new List<SqlParameter>();

            if (!string.IsNullOrEmpty(birim))
            {
                whereClause += " AND Birim = @birim";
                parameters.Add(new SqlParameter("@birim", birim));
            }
            if (!string.IsNullOrEmpty(yil))
            {
                whereClause += " AND Yil = @yil";
                parameters.Add(new SqlParameter("@yil", yil));
            }
            if (!string.IsNullOrEmpty(filename))
            {
                whereClause += " AND FileName = @filename";
                parameters.Add(new SqlParameter("@filename", filename));
            }

            string sql;
            if (queryVector != null)
            {
                var vectorJson = "[" + string.Join(",", queryVector.Select(f => f.ToString("F8"))) + "]";
                parameters.Add(new SqlParameter("@queryVector", vectorJson));
                sql = $@"
                    SELECT TOP ({k}) Content, FileName, Birim, Yil,
                        VECTOR_DISTANCE('cosine', CAST(@queryVector AS VECTOR({VectorDimension})), Vector) AS distance
                    FROM {_tableName}
                    WHERE {whereClause} AND Vector IS NOT NULL
                    ORDER BY distance ASC";
            }
            else
            {
                sql = $@"
                    SELECT TOP ({k}) Content, FileName, Birim, Yil
                    FROM {_tableName}
                    WHERE {whereClause}
                    ORDER BY IndexedAt DESC";
            }

            var chunks = new List<string>();
            using var conn = new SqlConnection(_connectionString);
            await conn.OpenAsync();
            using var cmd = new SqlCommand(sql, conn);
            cmd.Parameters.AddRange(parameters.ToArray());
            using var reader = await cmd.ExecuteReaderAsync();

            while (await reader.ReadAsync())
            {
                var content = reader.GetString(0);
                var fn = reader.GetString(1);
                chunks.Add($"[Kaynak: {fn}]\n{content}");
            }

            return string.Join("\n\n---\n\n", chunks);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Vektör arama hatası");
            return string.Empty;
        }
    }

    /// <summary>
    /// İşlenmiş markdown dosyalarını indeksler.
    /// Python'daki VectorStore.index_documents() metodunun .NET karşılığı.
    /// </summary>
    public async Task<int> IndexDocumentsAsync(string dataPath, bool forceReindex = false)
    {
        await EnsureTableExistsAsync();
        var processedDir = Path.Combine(dataPath, "processed");
        if (!Directory.Exists(processedDir))
        {
            _logger.LogWarning("processed/ dizini bulunamadı: {Path}", processedDir);
            return 0;
        }

        var indexedCount = 0;
        foreach (var mdFile in Directory.GetFiles(processedDir, "*.md"))
        {
            try
            {
                var filename = Path.GetFileName(mdFile);
                var content = await File.ReadAllTextAsync(mdFile);
                if (string.IsNullOrWhiteSpace(content)) continue;

                var parts = Path.GetFileNameWithoutExtension(mdFile).Split('_');
                var birim = parts.Length > 0 ? parts[0] : null;
                var yil = parts.Length > 1 && parts[1].All(char.IsDigit) ? parts[1] : null;
                var tur = parts.Length > 2 ? string.Join(" ", parts[2..]) : null;

                // ℹ️ IMPORTANT: Always clear OLD data for a file to prevent duplicates
                await DeleteFileVectorsAsync(filename);

                var chunks = ChunkText(content);
                var embeddingTasks = chunks
                    .Where(c => c.Text.Length >= 50)
                    .Select(async c => 
                    {
                        try 
                        {
                            var vector = await EmbedAsync(c.Text);
                            return new { c.Text, c.SectionTitle, Vector = vector };
                        }
                        catch (Exception ex)
                        {
                            _logger.LogError(ex, "Embedding error for chunk in {File}", filename);
                            return null;
                        }
                    });

                _logger.LogInformation("⏳ Vectorizing {Count} chunks for {File} in parallel...", chunks.Count, filename);
                var results = await Task.WhenAll(embeddingTasks);

                foreach (var res in results)
                {
                    if (res == null) continue;
                    await InsertVectorAsync(filename, res.Text, res.Vector, birim, yil, tur, res.SectionTitle);
                    indexedCount++;
                }

                _logger.LogInformation("✅ Indexed: {File} — {Count} chunks", filename, chunks.Count);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Indexing error: {File}", mdFile);
            }
        }

        return indexedCount;
    }

    /// <summary>
    /// Koleksiyon bilgisi. Python'daki get_collection_info() karşılığı.
    /// </summary>
    public async Task<Dictionary<string, object>> GetCollectionInfoAsync()
    {
        try
        {
            using var conn = new SqlConnection(_connectionString);
            await conn.OpenAsync();
            using var cmd = new SqlCommand($"SELECT COUNT(*) FROM {_tableName}", conn);
            var count = (int)await cmd.ExecuteScalarAsync();
            return new Dictionary<string, object>
            {
                ["toplam_nokta"] = count,
                ["durum"] = $"SQL Server 2025 — {_tableName} ({count} vektör)",
                ["tablo"] = _tableName
            };
        }
        catch (Exception ex)
        {
            return new Dictionary<string, object>
            {
                ["toplam_nokta"] = 0,
                ["durum"] = $"Hata: {ex.Message}",
                ["tablo"] = _tableName
            };
        }
    }

    // ── Private Helpers ──────────────────────────────────────────

    /// <summary>Ollama REST API ile embedding üretimi.</summary>
    private async Task<float[]> EmbedAsync(string text)
    {
        var body = JsonSerializer.Serialize(new { model = _embeddingModel, prompt = text });
        var content = new StringContent(body, Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync($"{_ollamaBaseUrl}/api/embeddings", content);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);
        return doc.RootElement.GetProperty("embedding")
            .EnumerateArray()
            .Select(e => e.GetSingle())
            .ToArray();
    }

    private async Task InsertVectorAsync(string fileName, string content, float[] vector,
        string? birim, string? yil, string? tur, string? sectionTitle)
    {
        var vectorJson = "[" + string.Join(",", vector.Select(f => f.ToString("F8"))) + "]";
        var sql = $@"
            INSERT INTO {_tableName} (FileName, Birim, Yil, Tur, BolumBasligi, Content, Vector)
            VALUES (@fn, @birim, @yil, @tur, @bolum, @content, CAST(@vector AS VECTOR({VectorDimension})))";

        using var conn = new SqlConnection(_connectionString);
        await conn.OpenAsync();
        using var cmd = new SqlCommand(sql, conn);
        cmd.Parameters.AddWithValue("@fn", fileName);
        cmd.Parameters.AddWithValue("@birim", (object?)birim ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@yil", (object?)yil ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@tur", (object?)tur ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@bolum", (object?)sectionTitle ?? DBNull.Value);
        cmd.Parameters.AddWithValue("@content", content);
        cmd.Parameters.AddWithValue("@vector", vectorJson);
        await cmd.ExecuteNonQueryAsync();
    }

    private async Task DeleteFileVectorsAsync(string filename)
    {
        using var conn = new SqlConnection(_connectionString);
        await conn.OpenAsync();
        using var cmd = new SqlCommand($"DELETE FROM {_tableName} WHERE FileName = @fn", conn);
        cmd.Parameters.AddWithValue("@fn", filename);
        await cmd.ExecuteNonQueryAsync();
    }

    private static List<(string Text, string? SectionTitle)> ChunkText(
        string text, int chunkSize = 1000, int overlap = 200)
    {
        var chunks = new List<(string, string?)>();
        var lines = text.Split('\n');
        var current = new StringBuilder();
        string? currentSection = null;

        foreach (var line in lines)
        {
            if (line.StartsWith("## ")) currentSection = line[3..].Trim();
            current.AppendLine(line);

            if (current.Length >= chunkSize)
            {
                chunks.Add((current.ToString().Trim(), currentSection));
                var all = current.ToString();
                current.Clear();
                if (overlap > 0 && all.Length > overlap)
                    current.Append(all[^overlap..]);
            }
        }
        if (current.Length > 50)
            chunks.Add((current.ToString().Trim(), currentSection));

        return chunks;
    }
}
