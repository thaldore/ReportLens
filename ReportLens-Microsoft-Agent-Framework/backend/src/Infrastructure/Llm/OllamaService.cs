// ══════════════════════════════════════════════════════════════════
// ReportLens MAF Backend — Infrastructure: Ollama LLM Service
// Semantic Kernel ile Ollama entegrasyonu.
// Python'daki Agno framework'un .NET karshiligi.
// ══════════════════════════════════════════════════════════════════
#pragma warning disable SKEXP0001, SKEXP0010, SKEXP0070

using Microsoft.SemanticKernel;
using Microsoft.SemanticKernel.ChatCompletion;
using Microsoft.SemanticKernel.Connectors.OpenAI;
using ReportLens.Application.Interfaces;
using System.Text;
using System.Text.Json;

namespace ReportLens.Infrastructure.Llm;

/// <summary>
/// Ollama ile iletisim kuran LLM servisi.
/// Semantic Kernel Kernel nesnesi uzerinden calisir.
/// Text generation ve embedding API'leri desteklenir.
/// Python'daki Agno/Ollama kombinasyonunun .NET karsiligi.
/// </summary>
public class OllamaService : ILlmService
{
    private readonly Kernel _kernel;
    private readonly HttpClient _httpClient;
    private readonly string _ollamaBaseUrl;
    private readonly string _modelId;
    private readonly string _embeddingModel;
    private readonly ILogger<OllamaService> _logger;

    public OllamaService(
        Kernel kernel,
        IConfiguration configuration,
        IHttpClientFactory httpClientFactory,
        ILogger<OllamaService> logger)
    {
        _kernel = kernel;
        _ollamaBaseUrl = configuration["Ollama:BaseUrl"] ?? "http://localhost:11434";
        _modelId = configuration["Ollama:ModelId"] ?? "llama3.1:8b";
        _embeddingModel = configuration["Ollama:EmbeddingModel"] ?? "nomic-embed-text";
        _httpClient = httpClientFactory.CreateClient("ollama");
        _logger = logger;
    }

    /// <summary>
    /// Semantic Kernel uzerinden LLM metin uretimi.
    /// System prompt + user prompt kombinasyonu.
    /// </summary>
    public async Task<string> GenerateAsync(string systemPrompt, string userPrompt, double temperature = 0.1)
    {
        try
        {
            var chatService = _kernel.GetRequiredService<IChatCompletionService>();
            var history = new ChatHistory();
            history.AddSystemMessage(systemPrompt);
            history.AddUserMessage(userPrompt);

            var settings = new OpenAIPromptExecutionSettings
            {
                Temperature = temperature,
                MaxTokens = 4096,
            };

            var result = await chatService.GetChatMessageContentAsync(history, settings, _kernel);
            return result.Content ?? string.Empty;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "LLM generation hatasi");
            throw;
        }
    }

    /// <summary>
    /// Ollama REST API uzerinden embedding uretimi.
    /// nomic-embed-text modeli ile 768 boyutlu vektor.
    /// </summary>
    public async Task<float[]> EmbedAsync(string text)
    {
        var requestBody = JsonSerializer.Serialize(new
        {
            model = _embeddingModel,
            prompt = text
        });

        var content = new StringContent(requestBody, Encoding.UTF8, "application/json");
        var response = await _httpClient.PostAsync($"{_ollamaBaseUrl}/api/embeddings", content);
        response.EnsureSuccessStatusCode();

        var json = await response.Content.ReadAsStringAsync();
        using var doc = JsonDocument.Parse(json);

        if (doc.RootElement.TryGetProperty("embedding", out var embeddingElement))
        {
            return embeddingElement.EnumerateArray()
                .Select(e => e.GetSingle())
                .ToArray();
        }

        throw new InvalidOperationException("Embedding response has no 'embedding' field.");
    }

    /// <summary>
    /// Ollama servisine baglanti kontrolu.
    /// </summary>
    public async Task<bool> CheckConnectionAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync($"{_ollamaBaseUrl}/api/tags");
            if (!response.IsSuccessStatusCode) return false;

            var json = await response.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(json);
            var models = doc.RootElement.GetProperty("models").EnumerateArray()
                .Select(m => m.GetProperty("name").GetString() ?? "")
                .ToList();

            var hasLlm = models.Any(m => m.Contains(_modelId.Split(':')[0]));
            var hasEmbed = models.Any(m => m.Contains(_embeddingModel.Split(':')[0]));

            if (!hasLlm) _logger.LogWarning("LLM modeli '{Model}' bulunamadi! Lutfen 'ollama pull {Model}' calistirin.", _modelId, _modelId);
            if (!hasEmbed) _logger.LogWarning("Embedding modeli '{Model}' bulunamadi! Lutfen 'ollama pull {Model}' calistirin.", _embeddingModel, _embeddingModel);

            return true;
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex, "Ollama baglanti kontrolu basarisiz — servis hazir degil veya ulasılamıyor.");
            return false;
        }
    }

    /// <summary>
    /// Yuklu Ollama modellerini listeler.
    /// </summary>
    public async Task<List<string>> GetLoadedModelsAsync()
    {
        try
        {
            var response = await _httpClient.GetAsync($"{_ollamaBaseUrl}/api/tags");
            if (!response.IsSuccessStatusCode) return [];

            var json = await response.Content.ReadAsStringAsync();
            using var doc = JsonDocument.Parse(json);
            return doc.RootElement.GetProperty("models").EnumerateArray()
                .Select(m => m.GetProperty("name").GetString() ?? "")
                .ToList();
        }
        catch
        {
            return [];
        }
    }
}
