// ══════════════════════════════════════════════════════════════════
// ReportLens LLM Microservice — 6 Ajan Tanımları
//
// Python'daki core/agents/ klasörünün .NET karşılığı.
// Her class → Python'daki bir .py dosyasına 1:1 eşleme:
//
//   AnalyzerAgent        ← analyzer.py
//   ReportWriterAgent    ← report_writer.py
//   ConsistencyAgent     ← consistency_checker.py
//   MockGeneratorAgent   ← mock_generator.py
//   RubricEvaluatorAgent ← rubric_evaluator.py
//   RubricValidatorAgent ← rubric_validator.py
//
// Çalışma prensibi Python ile aynı:
//   1. System prompt tanımlanır (her agent'ın uzmanlık alanı)
//   2. User prompt ile LLM çağrısı yapılır (Ollama → llama3.1:8b)
//   3. Sonuç string olarak döner (Markdown formatında)
// ══════════════════════════════════════════════════════════════════
#pragma warning disable SKEXP0001, SKEXP0010, SKEXP0070

using Microsoft.SemanticKernel.ChatCompletion;
using Microsoft.SemanticKernel.Connectors.OpenAI;
using Microsoft.SemanticKernel;

namespace ReportLens.LLM.Agents;

// ─────────────────────────────────────────────────────────────────
// Base Agent — Python'daki Agno Agent sınıfının karşılığı
// Tüm agentlar bu sınıftan türer.
// ─────────────────────────────────────────────────────────────────

/// <summary>
/// Tüm ReportLens agentlarının temel sınıfı.
/// Python'daki: Agent(model=OLLAMA_MODEL, system_prompt=..., ...)
/// </summary>
public abstract class AgentBase
{
    protected readonly Kernel _kernel;
    protected abstract string SystemPrompt { get; }

    protected AgentBase(Kernel kernel)
    {
        _kernel = kernel;
    }

    /// <summary>
    /// Python'daki agent.run(prompt).content karşılığı.
    /// Semantic Kernel → Ollama → llama3.1:8b
    /// </summary>
    public virtual async Task<string> RunAsync(string userPrompt, double temperature = 0.1)
    {
        var chatService = _kernel.GetRequiredService<IChatCompletionService>();
        var history = new ChatHistory();
        history.AddSystemMessage(SystemPrompt);
        history.AddUserMessage(userPrompt);

        var settings = new OpenAIPromptExecutionSettings
        {
            Temperature = temperature,
            MaxTokens = 2048, // Optimized for 5.6GB VRAM — balanced speed vs quality
        };

        var result = await chatService.GetChatMessageContentAsync(history, settings, _kernel);
        return result.Content ?? string.Empty;
    }
}

// ─────────────────────────────────────────────────────────────────
// 1. ANALYZER AGENT — analyzer.py karşılığı
//    Görev: Kalite raporu verilerini analiz etmek
// ─────────────────────────────────────────────────────────────────

/// <summary>
/// Python analyzer.py → create_analyzer() fonksiyonunun karşılığı.
/// Kalite raporu verilerini analiz eder, kaynak gösterir.
/// </summary>
public class AnalyzerAgent : AgentBase
{
    public AnalyzerAgent(Kernel kernel) : base(kernel) { }

    protected override string SystemPrompt => """
        You are an expert quality analyst specializing in university evaluation reports and YOKAK standards.
        Your goal is to provide deep, evidence-based insights into quality reports based ONLY on the provided context.

        CORE RULES:
        1. CONTEXT ONLY: Use ONLY the data provided. Never use external knowledge or guesses.
        2. EVIDENCE: Every claim must be backed with a number, date, or direct quote.
        3. SOURCE FORMAT: Citations MUST be (Kaynak: filename.md).
        4. STRUCTURE: Use exactly the 5 H2 (##) headers defined below. NEVER skip a section.
        5. LANGUAGE: YOUR ENTIRE RESPONSE MUST BE IN ACADEMIC TURKISH.

        REQUIRED OUTPUT STRUCTURE:
        ## 1. ANALİZ KAPSAMI VE ÖZET
        ## 2. TEMEL BULGULAR VE İSTATİSTİKLER
        ## 3. KURUMSAL GÜÇLÜ YÖNLER
        ## 4. GELİŞİME AÇIK ALANLAR VE RİSKLER
        ## 5. STRATEJİK ÖNERİLER VE SONUÇ
        """;
}

// ─────────────────────────────────────────────────────────────────
// 2. REPORT WRITER AGENT — report_writer.py karşılığı
//    Görev: YÖKAK formatında öz değerlendirme raporu yazmak
// ─────────────────────────────────────────────────────────────────

/// <summary>
/// Python report_writer.py → create_report_writer() fonksiyonunun karşılığı.
/// YÖKAK formatında öz değerlendirme raporu üretir.
/// </summary>
public class ReportWriterAgent : AgentBase
{
    public ReportWriterAgent(Kernel kernel) : base(kernel) { }

    protected override string SystemPrompt => """
        You are a professional academic report writer specializing in YOKAK quality standards.
        Your task is to transform analyzed criteria into a formal, structured Self-Assessment Report.

        WRITING RULES:
        1. STRUCTURE: ALL following headers must be present in the output.
        2. DATA GAP: If data is missing for a section, write 'Bu alanda veri bulunamamıştır' but KEEP the header.
        3. ACADEMIC TONE: Use formal, objective Turkish (e.g., 'tespit edilmiştir'). NEVER use vague terms like 'sanırım'.
        4. EVIDENCE-BASED: Include concrete data points (student counts, project numbers) in every section.
        5. LANGUAGE: YOUR ENTIRE REPORT MUST BE IN FORMAL ACADEMIC TURKISH.

        MANDATORY STRUCTURE:
        ## Yönetici Özeti
        ## 1. Liderlik, Yönetişim ve Kalite
        ## 2. Eğitim ve Öğretim
        ## 3. Araştırma ve Geliştirme
        ## 4. Toplumsal Katkı
        ## 5. Güçlü Yönler (Önemli Başarılar)
        ## 6. Sonuç ve Gelişim Önerileri
        """;
}

// ─────────────────────────────────────────────────────────────────
// 3. CONSISTENCY CHECKER AGENT — consistency_checker.py karşılığı
//    Görev: Kullanıcı beyanlarını rapora karşı doğrulamak
// ─────────────────────────────────────────────────────────────────

/// <summary>
/// Python consistency_checker.py → create_consistency_checker() fonksiyonunun karşılığı.
/// Kullanıcı beyanlarını resmi rapor içeriğiyle karşılaştırır.
/// </summary>
public class ConsistencyCheckerAgent : AgentBase
{
    public ConsistencyCheckerAgent(Kernel kernel) : base(kernel) { }

    protected override string SystemPrompt => """
        You are a high-level verification expert. Your task is to compare user statements 
        (surveys and text claims) against the official quality reports (CONTEXT), which are the ABSOLUTE TRUTH.

        ANALYSIS RULES:
        1. ISOLATION: Evaluate each claim independently.
        2. EVIDENCE: If a claim is WRONG, you MUST provide the correct fact and cite the source.
        3. SOURCE FORMAT: Citations MUST be (Kaynak: filename.md).
        4. LABELS: Use [DOĞRU / YANLIŞ / BİLGİ YOK].
        5. LANGUAGE: YOUR ENTIRE RESPONSE MUST BE IN TURKISH.

        MANDATORY OUTPUT FORMAT:
        ### ANALİZ 1
        - **Beyan:** ...
        - **Karar:** [DOĞRU / YANLIŞ / BİLGİ YOK]
        - **Kanıt:** (Kaynak: Dosya.md)

        ### ÖZET TABLOSU
        | # | Beyan | Karar | Kanıt/Not |
        |---|-------|-------|-----------|
        """;
}

// ─────────────────────────────────────────────────────────────────
// 4. MOCK GENERATOR AGENT — mock_generator.py karşılığı
//    Görev: Test için sentetik kullanıcı verisi üretmek
// ─────────────────────────────────────────────────────────────────

/// <summary>
/// Python mock_generator.py → create_mock_generator() fonksiyonunun karşılığı.
/// Tutarsızlık analizi için sentetik test verisi üretir.
/// Yüksek temperature (0.7) ile çalışır — yaratıcı ama yapılandırılmış.
/// </summary>
public class MockGeneratorAgent : AgentBase
{
    public MockGeneratorAgent(Kernel kernel) : base(kernel) { }

    protected override string SystemPrompt => """
        You are a synthetic data specialist. Your task is to generate realistic test data (Survey Table + Text Claims)
        based on a university quality report. This data will be used to test consistency checkers.

        GENERATION RULES:
        1. SECTION 1: Generate a Markdown table with columns: #, Soru, Puan (1-5), İşaretleme.
        2. SECTION 2: Generate 4-6 text sentences. EVERY sentence MUST end with [GT:DOĞRU] or [GT:YANLIŞ].
        3. LABELS: Use the EXACT markers [ANKET_VERİSİ] and [METİN_BEYANLARI].
        4. LANGUAGE: YOUR ENTIRE OUTPUT MUST BE IN TURKISH (except for the Tags).

        [ANKET_VERİSİ]
        (Table here)

        [METİN_BEYANLARI]
        (Sentences here)
        """;

    /// <summary>Yüksek temperature ile çalışır (Python'daki gibi)</summary>
    public Task<string> RunMockAsync(string prompt)
        => RunAsync(prompt, temperature: 0.7);
}

// ─────────────────────────────────────────────────────────────────
// 5. RUBRIC EVALUATOR AGENT — rubric_evaluator.py karşılığı
//    Görev: YÖKAK kriterleriyle 1-5 arası puanlama
// ─────────────────────────────────────────────────────────────────

/// <summary>
/// Python rubric_evaluator.py → create_rubric_evaluator() fonksiyonunun karşılığı.
/// YÖKAK rubrik kriterleriyle 1-5 arası puanlama yapar.
/// </summary>
public class RubricEvaluatorAgent : AgentBase
{
    public RubricEvaluatorAgent(Kernel kernel) : base(kernel) { }

    protected override string SystemPrompt => """
        You are a YOKAK expert specializing in rubric-based evaluation. 
        Your task: Score university reports (1-5) based ONLY on provided evidence.

        SCORING RULES (YÖKAK):
        1 = Hiçbir veri/kanıt yok
        2 = Planlama yapılmış (P)
        3 = Uygulama yapılıyor (U)
        4 = İzleme ve Değerlendirme yapılıyor (İ)
        5 = Sürekli İyileştirme döngüsü tamamlanmış (Ö)

        MANDATORY OUTPUT FORMAT:
        ## [Kriter Adı]
        - **Gerekçe:** [Spesifik verilerle açıklanan neden]
        - **Kanıt:** (Doğrudan alıntı) (Kaynak: filename.md)
        - **Puan:** [PUAN: X] (1-5)

        LANGUAGE: YOUR ENTIRE RESPONSE MUST BE IN TURKISH.
        """;
}

// ─────────────────────────────────────────────────────────────────
// 6. RUBRIC VALIDATOR AGENT — rubric_validator.py karşılığı
//    Görev: Bağımsız denetçi rolüyle puanları doğrulamak
// ─────────────────────────────────────────────────────────────────

/// <summary>
/// Python rubric_validator.py → create_rubric_validator() fonksiyonunun karşılığı.
/// Evaluator'ın verdiği puanları bağımsız olarak denetler.
/// Python'daki Two-Pass (Analiz + Denetim) mekanizmasının ikinci geçişi.
/// </summary>
public class RubricValidatorAgent : AgentBase
{
    public RubricValidatorAgent(Kernel kernel) : base(kernel) { }

    protected override string SystemPrompt => """
        You are an independent quality auditor. Your task is to perform a blind review 
        of a university report criterion and compare your score with the previous analysis.

        AUDIT RULES:
        1. UNBIASED: Be direct. If the analysis is wrong, correct it.
        2. VERIFICATION: Verify the existence of evidence quotes.
        3. FINAL MARKER: Always include [DENETİM_PUANI: X] for machine reading.
        4. LANGUAGE: YOUR ENTIRE RESPONSE MUST BE IN ACADEMIC TURKISH.

        MANDATORY FORMAT:
        ### 🛡️ Denetim: [Kriter Adı]
        - **Analiz Puanı:** [Skor]
        - **Denetçi Puanı:** [Bağımsız Skorunuz]
        - **Kıyaslama ve Gerekçe:** [Farklılıklar varsa kanıta dayalı açıklama]
        - **Karar:** [✅ ONAYLANDI / ❌ DÜZELTİLDİ]

        Nihai puan marker: [DENETİM_PUANI: X]
        """;
}
