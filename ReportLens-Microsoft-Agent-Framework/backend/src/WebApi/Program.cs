// ══════════════════════════════════════════════════════════════════
// ReportLens MAF Backend — WebApi: Program.cs
// Clean Architecture + Modular Monolith DI kayitlari.
// ══════════════════════════════════════════════════════════════════
#pragma warning disable SKEXP0001, SKEXP0010, SKEXP0070

using Microsoft.SemanticKernel;
using ReportLens.Application.Interfaces;
using ReportLens.Application.Services;

using ReportLens.Infrastructure.Llm;
using ReportLens.Infrastructure.Processing;
using ReportLens.Infrastructure.VectorSearch;

var builder = WebApplication.CreateBuilder(args);

// ── Logging ───────────────────────────────────────────────────────
builder.Logging.ClearProviders();
builder.Logging.AddConsole();
builder.Logging.SetMinimumLevel(LogLevel.Information);

// ── HTTP Client (Ollama icin) ─────────────────────────────────────
builder.Services.AddHttpClient("ollama", client =>
{
    var ollamaUrl = builder.Configuration["Ollama:BaseUrl"] ?? "http://localhost:11434";
    client.BaseAddress = new Uri(ollamaUrl);
    client.Timeout = TimeSpan.FromHours(1); // 1-hour timeout for long indexing or complex AI tasks
});

// ── HTTP Client (MAF LLM Microservice icin) ──────────────────────
builder.Services.AddHttpClient("LLM_Microservice", client =>
{
    var llmUrl = builder.Configuration["LLM:BaseUrl"] ?? "http://localhost:8002";
    client.BaseAddress = new Uri(llmUrl);
    client.Timeout = TimeSpan.FromHours(1);
});

// ── Semantic Kernel (Ollama Chat Completion) ──────────────────────
var ollamaBaseUrl = builder.Configuration["Ollama:BaseUrl"] ?? "http://localhost:11434";
var modelId = builder.Configuration["Ollama:ModelId"] ?? "llama3.1:8b";

builder.Services.AddSingleton(sp =>
{
    var kernel = Kernel.CreateBuilder()
        .AddOpenAIChatCompletion(
            modelId: modelId,
            endpoint: new Uri(ollamaBaseUrl + "/"),
            apiKey: "ollama" // Ollama gercek API key gerektirmiyor
        )
        .Build();
    return kernel;
});

// ── Infrastructure Servisleri ─────────────────────────────────────
builder.Services.AddSingleton<ILlmService, OllamaService>();
builder.Services.AddScoped<IVectorSearchService, MssqlVectorSearchService>();
builder.Services.AddScoped<IDocumentProcessor, DocumentProcessor>();

// ── Application Servisleri ────────────────────────────────────────
builder.Services.AddScoped<IAnalysisService, QualityBrainService>();

// ── WebApi Altyapisi ─────────────────────────────────────────────
builder.Services.AddControllers().AddJsonOptions(options =>
{
    options.JsonSerializerOptions.PropertyNameCaseInsensitive = true;
});
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen(c =>
{
    c.SwaggerDoc("v1", new()
    {
        Title = "ReportLens MAF API",
        Version = "v1",
        Description = "Microsoft Agent Framework ile Universite Kalite Raporu Analiz Sistemi. " +
                      "Clean Architecture + Semantic Kernel + SQL Server 2025 VECTOR."
    });
});

builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowAll", policy =>
        policy.AllowAnyOrigin().AllowAnyMethod().AllowAnyHeader());
});

// ── Statik Frontend Dosyalari (Nginx degilse) ─────────────────────
// Docker'da Nginx kullanıldığı için genellikle devre disi.
// Yerel gelistirme icin: builder.Services.AddStaticFiles();

var app = builder.Build();

// ── Baslarken Tablo Olustur ──────────────────────────────────────
using (var scope = app.Services.CreateScope())
{
    try
    {
        var vectorSearch = scope.ServiceProvider.GetRequiredService<IVectorSearchService>();
        if (vectorSearch is MssqlVectorSearchService mssqlService)
        {
            await mssqlService.EnsureTableExistsAsync();
        }

        // Ollama baglanti kontrolu
        var llm = scope.ServiceProvider.GetRequiredService<ILlmService>();
        var connected = await llm.CheckConnectionAsync();
        if (!connected)
        {
            app.Logger.LogWarning(
                "UYARI: Ollama servisi hazir degil. Analizler calistiginda yeniden denenecek. " +
                "GPU yoksa CPU modunda (yavas) calisacaktir.");
        }
    }
    catch (Exception ex)
    {
        app.Logger.LogWarning(ex, "Baslangic kontrolu basarisiz — uygulama yine de baslatiliyor.");
    }
}

// ── Middleware Pipeline ───────────────────────────────────────────
if (app.Environment.IsDevelopment() || app.Environment.IsEnvironment("Production"))
{
    app.UseSwagger();
    app.UseSwaggerUI(c =>
    {
        c.SwaggerEndpoint("/swagger/v1/swagger.json", "ReportLens MAF API v1");
        c.RoutePrefix = "swagger";
    });
}

app.UseCors("AllowAll");
app.MapControllers();

// Health check endpoint
app.MapGet("/health", () => Results.Ok(new
{
    status = "healthy",
    service = "reportlens-maf-backend",
    timestamp = DateTime.UtcNow
}));

// Root status endpoint to prevent 404 confusion
app.MapGet("/", () => Results.Ok(new
{
    message = "ReportLens MAF Backend is Running",
    environment = builder.Environment.EnvironmentName,
    docs = "/swagger",
    health = "/health",
    timestamp = DateTime.UtcNow
}));

app.Run();
