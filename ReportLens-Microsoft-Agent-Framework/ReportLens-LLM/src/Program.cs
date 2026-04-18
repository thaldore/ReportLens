// ══════════════════════════════════════════════════════════════════
// ReportLens LLM Microservice — Program.cs (Tam DI Kaydı)
// Port: 8080 (docker-compose.yml ile dış port 8002'ye map)
// ══════════════════════════════════════════════════════════════════
#pragma warning disable SKEXP0001, SKEXP0010, SKEXP0070

using Microsoft.SemanticKernel;
using ReportLens.LLM.Brain;
using ReportLens.LLM.VectorSearch;

var builder = WebApplication.CreateBuilder(args);

// ── Logging ───────────────────────────────────────────────────────
builder.Logging.ClearProviders();
builder.Logging.AddConsole();
builder.Logging.SetMinimumLevel(LogLevel.Information);

// ── HTTP Client (Ollama için) ─────────────────────────────────────
builder.Services.AddHttpClient("ollama", client =>
{
    var ollamaUrl = builder.Configuration["Ollama:BaseUrl"] ?? "http://localhost:11434";
    client.BaseAddress = new Uri(ollamaUrl);
    client.Timeout = TimeSpan.FromMinutes(5);
});

// ── Semantic Kernel — Ollama Chat Completion ──────────────────────
var ollamaBaseUrl = builder.Configuration["Ollama:BaseUrl"] ?? "http://localhost:11434";
var modelId = builder.Configuration["Ollama:ModelId"] ?? "llama3.1:8b";

builder.Services.AddSingleton(_ =>
{
    return Kernel.CreateBuilder()
        .AddOpenAIChatCompletion(
            modelId: modelId,
            endpoint: new Uri(ollamaBaseUrl + "/"),
            apiKey: "ollama"  // Ollama gerçek key gerektirmiyor
        )
        .Build();
});

// ── VectorStore — SQL Server 2025 VECTOR ─────────────────────────
builder.Services.AddSingleton<VectorStore>();

// ── QualityBrain — 6 Agent Orkestratörü ──────────────────────────
builder.Services.AddSingleton<QualityBrain>();

// ── WebApi Altyapısı ─────────────────────────────────────────────
builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new()
    {
        Title = "ReportLens LLM Microservice",
        Version = "v1",
        Description = "6 Agent (Analyzer, ReportWriter, ConsistencyChecker, MockGenerator, RubricEvaluator, RubricValidator) + QualityBrain Orkestratörü. " +
                      "SQL Server 2025 VECTOR_DISTANCE semantik arama."
    });
});

builder.Services.AddCors(options =>
    options.AddDefaultPolicy(policy =>
        policy.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader()));

var app = builder.Build();

// ── Başlarken Tablo Oluştur ──────────────────────────────────────
using (var scope = app.Services.CreateScope())
{
    try
    {
        var vectorStore = scope.ServiceProvider.GetRequiredService<VectorStore>();
        await vectorStore.EnsureTableExistsAsync();
        app.Logger.LogInformation("MAF LLM Mikroservisi hazır. Tablo: MAF_DocumentVectors");
    }
    catch (Exception ex)
    {
        // Hata kritik değil — uygulama çalışmaya devam eder
        app.Logger.LogWarning(ex, "Veritabanı bağlantısı kurulamadı — uygulama yine de başlatılıyor.");
    }
}

// ── Middleware Pipeline ───────────────────────────────────────────
app.UseSwagger();
app.UseSwaggerUI(c =>
{
    c.SwaggerEndpoint("/swagger/v1/swagger.json", "ReportLens LLM Microservice v1");
    c.RoutePrefix = "swagger";
});

app.UseCors();
app.MapControllers();

app.MapGet("/health", () => Results.Ok(new
{
    status = "healthy",
    service = "reportlens-maf-llm",
    agents = new[] { "AnalyzerAgent", "ReportWriterAgent", "ConsistencyCheckerAgent",
                     "MockGeneratorAgent", "RubricEvaluatorAgent", "RubricValidatorAgent" },
    brain = "QualityBrain",
    timestamp = DateTime.UtcNow
}));

app.Run();
