// ══════════════════════════════════════════════════════════════════
// ReportLens LLM Microservice — QualityBrain (Orkestrasyon)
//
// Python'daki core/brain.py → QualityBrain sınıfının karşılığı.
// Tüm 6 agent'ı yönetir, vektör araması yapar, sonuçları birleştirir.
//
// Python QualityBrain.__init__:
//   self.analyzer = create_analyzer(model, ollama_url)
//   self.report_writer = create_report_writer(...)
//   self.consistency_checker = create_consistency_checker(...)
//   self.mock_generator = create_mock_generator(...)
//   self.rubric_evaluator = create_rubric_evaluator(...)
//   self.rubric_validator = create_rubric_validator(...)
// ══════════════════════════════════════════════════════════════════

using Microsoft.SemanticKernel;
using ReportLens.LLM.Agents;
using ReportLens.LLM.VectorSearch;
using System.Text.RegularExpressions;

namespace ReportLens.LLM.Brain;

/// <summary>
/// Ana kalite analiz orkestratörü.
/// Python brain.py → QualityBrain sınıfının tam .NET karşılığı.
/// Tüm analiz çağrıları buradan geçer.
/// </summary>
public class QualityBrain
{
    // ── 6 Agent — Python'daki ile birebir ────────────────────────
    private readonly AnalyzerAgent _analyzer;
    private readonly ReportWriterAgent _reportWriter;
    private readonly ConsistencyCheckerAgent _consistencyChecker;
    private readonly MockGeneratorAgent _mockGenerator;
    private readonly RubricEvaluatorAgent _rubricEvaluator;
    private readonly RubricValidatorAgent _rubricValidator;

    // ── VectorStore — Python vector_store.py karşılığı ───────────
    private readonly VectorStore _vectorStore;
    private readonly ILogger<QualityBrain> _logger;

    // ── YÖKAK Rubrik Kriterleri — Python config.py'deki RUBRIC_CRITERIA ──
    private static readonly Dictionary<string, string> RubricCriteria = new()
    {
        ["A. Liderlik, Yönetişim ve Kalite"] =
            "Misyon, vizyon, stratejik amaçlar, yönetim sistemleri, paydaş katılımı ve uluslararasılaşma süreçleri.",
        ["B. Eğitim ve Öğretim"] =
            "Programların tasarımı, yürütülmesi, öğrenme kaynakları, öğretim kadrosu ve programların izlenmesi.",
        ["C. Araştırma ve Geliştirme"] =
            "Araştırma stratejisi, kaynakları, yetkinliği ve performansı.",
        ["D. Toplumsal Katkı"] =
            "Toplumsal katkı stratejisi, kaynakları ve performansı."
    };

    // ── Birim anahtar kelimeleri — Python config.py'deki BIRIM_KEYWORDS ──
    private static readonly Dictionary<string, string[]> BirimKeywords = new()
    {
        ["Fen"] = ["fen fakültesi", "biyoloji", "biyoteknoloji", "fizik bölümü", "kimya bölümü", "matematik"],
        ["IIBF"] = ["iibf", "iktisadi", "idari bilimler", "iktisat", "işletme", "maliye", "kamu yönetimi"],
        ["Mimarlık"] = ["mimarlık", "mimari", "peyzaj mimarlığı", "şehir ve bölge planlama", "iç mimarlık"],
        ["ITBF"] = ["itbf", "insan ve toplum bilimleri", "psikoloji", "sosyoloji", "tarih", "coğrafya"]
    };

    private static readonly Dictionary<string, string> BirimFullNames = new()
    {
        ["Fen"] = "Fen Fakültesi",
        ["IIBF"] = "İktisadi ve İdari Bilimler Fakültesi",
        ["ITBF"] = "İnsan ve Toplum Bilimleri Fakültesi",
        ["Mimarlık"] = "Mimarlık Fakültesi"
    };

    public QualityBrain(Kernel kernel, VectorStore vectorStore, ILogger<QualityBrain> logger)
    {
        // Python'daki create_xxx() factory fonksiyonlarının karşılığı
        _analyzer = new AnalyzerAgent(kernel);
        _reportWriter = new ReportWriterAgent(kernel);
        _consistencyChecker = new ConsistencyCheckerAgent(kernel);
        _mockGenerator = new MockGeneratorAgent(kernel);
        _rubricEvaluator = new RubricEvaluatorAgent(kernel);
        _rubricValidator = new RubricValidatorAgent(kernel);
        _vectorStore = vectorStore;
        _logger = logger;
    }

    // ── Yardımcı: Birim ve Yıl tespiti ──────────────────────────

    /// <summary>Python'daki detect_birim_from_query() karşılığı.</summary>
    public string? DetectBirim(string query)
    {
        var q = query.ToLowerInvariant();
        foreach (var (birim, keywords) in BirimKeywords)
            if (keywords.Any(kw => q.Contains(kw))) return birim;
        return null;
    }

    /// <summary>Python'daki detect_yil_from_query() karşılığı.</summary>
    public string? DetectYil(string query)
    {
        var match = Regex.Match(query, @"\b(20\d{2})\b");
        return match.Success ? match.Groups[1].Value : null;
    }

    private static string GetBirimFullName(string? birim)
        => birim != null && BirimFullNames.TryGetValue(birim, out var name) ? name : birim ?? "";

    // ══════════════════════════════════════════════════════════════
    // analyze() — Python QualityBrain.analyze() karşılığı
    // ══════════════════════════════════════════════════════════════

    /// <summary>
    /// Genel kalite analizi. Python'daki analyze() metodunun .NET karşılığı.
    /// Vektör araması → AnalyzerAgent → Markdown sonuç
    /// </summary>
    public async Task<(string Result, string? AutoBirim, string? AutoYil)> AnalyzeAsync(
        string query, string? birim = null, string? yil = null)
    {
        var autoBirim = birim ?? DetectBirim(query);
        var autoYil = yil ?? DetectYil(query);

        _logger.LogInformation("analyze() - Query: {Query}, Birim: {Birim}, Yil: {Yil}",
            query[..Math.Min(60, query.Length)], autoBirim, autoYil);

        var context = await _vectorStore.SearchAsync(query, k: 25, birim: autoBirim, yil: autoYil);
        if (string.IsNullOrWhiteSpace(context))
            return ("Bu konuda vektör veritabanında ilgili bilgi bulunamadı. Raporların yüklenip indekslendiğinden emin olun.", autoBirim, autoYil);

        var birimFull = GetBirimFullName(autoBirim);
        var birimInfo = autoBirim != null ? $"Birim filtresi: **{birimFull}** ({autoBirim})" : "Birim filtresi yok (tüm raporlar)";
        var yilInfo = autoYil != null ? $", Yıl filtresi: **{autoYil}**" : "";

        var prompt = $"""
            ### ANALYSIS FILTER: [{birimInfo}{yilInfo}]

            ### CONTEXT DATA (REPORT EXCERPTS):
            {context}

            ### TASK: Provide a detailed analysis of the question: '{query}' based ONLY on the data above.

            CORE RULES:
            1. EVIDENCE: Every claim or finding MUST include a source. Format: (Kaynak: filename.md)
            2. STRUCTURE: Use exactly the headers defined in the template.
            3. DATA-DRIVEN: Prioritize numerical data, statistics, and specific system names.
            4. LANGUAGE: YOUR ENTIRE RESPONSE MUST BE IN TURKISH.
            """;

        var result = await _analyzer.RunAsync(prompt);
        return (result, autoBirim, autoYil);
    }

    // ══════════════════════════════════════════════════════════════
    // analyze_single_report() — Python karşılığı
    // ══════════════════════════════════════════════════════════════

    /// <summary>
    /// Tek raporu detaylı analiz eder.
    /// Python'daki analyze_single_report() metodunun .NET karşılığı.
    /// </summary>
    public async Task<string> AnalyzeReportAsync(string filename)
    {
        _logger.LogInformation("analyze_single_report() - File: {File}", filename);

        // Birden fazla anchor ile bağlam topla (Python'daki gibi)
        var anchors = new[]
        {
            "Raporun genel özeti ve temel sayısal veriler",
            "Eğitim öğretim, güçlü yanlar ve gelişim alanları",
            "Araştırma geliştirme, toplumsal katkı ve gelecek hedefleri"
        };

        var contextParts = await Task.WhenAll(
            anchors.Select(a => _vectorStore.SearchAsync(a, k: 10, filename: filename)));
        var fullContext = string.Join("\n\n---\n\n", contextParts);

        var prompt = $"""
            ### DETAILED REPORT ANALYSIS: {filename}

            ### CONTEXT DATA (REPORT EXCERPTS):
            {fullContext}

            CORE RULES:
            1. EVIDENCE: Provide concrete evidence and data for each section.
            2. STRUCTURE: Use H2 (##) headers and full section names.
            3. CITATION: Use ONLY the format (Kaynak: {filename}).
            4. LANGUAGE: YOUR ENTIRE RESPONSE MUST BE IN TURKISH.

            ## 1. RAPOR TÜRÜ VE KAPSAMI
            ## 2. TEMEL SAYISAL VERİLER VE İSTATİSTİKLER
            ## 3. ANA BULGULAR VE DEĞERLENDİRME
            ## 4. GÜÇLÜ YÖNLER
            ## 5. ZAYIF YÖNLER VE RİSKLER
            ## 6. EYLEM PLANLARI VE HEDEFLER
            """;

        return await _analyzer.RunAsync(prompt);
    }

    // ══════════════════════════════════════════════════════════════
    // generate_self_evaluation() — Python karşılığı
    // ══════════════════════════════════════════════════════════════

    /// <summary>
    /// YÖKAK formatında öz değerlendirme raporu üretir.
    /// Python'daki generate_self_evaluation() metodunun .NET karşılığı.
    /// Her kriter için ayrı vektör araması → 4 kriter analizi → ReportWriter
    /// </summary>
    public async Task<string> GenerateSelfEvaluationAsync(string birim, string? yil = null)
    {
        var birimFull = GetBirimFullName(birim);
        _logger.LogInformation("generate_self_evaluation() - Birim: {Birim}, Yil: {Yil}", birim, yil);

        // Her kriter için sırayla analiz (Python'daki gibi — VRAM güvenliği)
        var criteriaAnalyses = new List<string>();
        foreach (var (criterionId, criterionDesc) in RubricCriteria)
        {
            _logger.LogDebug("Kriter analiz: {Criterion}", criterionId);
            var context = await _vectorStore.SearchAsync($"{criterionId} {criterionDesc}", k: 15, birim: birim, yil: yil);
            var prompt = $"""
                Unit: {birimFull} ({birim})
                Year: {yil ?? "All"}
                Quality Criterion: {criterionId}
                Criterion Description: {criterionDesc}
                Context Data:
                {context}

                TASK: Analyze the 'Strengths' and 'Areas for Improvement' for this specific criterion based ONLY on evidence.
                You MUST include at least one concrete data point or direct report excerpt.
                YOUR RESPONSE MUST BE IN ACADEMIC TURKISH.
                """;
            var analysis = await _analyzer.RunAsync(prompt);
            criteriaAnalyses.Add($"### {criterionId}\n{analysis[..Math.Min(2500, analysis.Length)]}");
        }

        var fullContext = string.Join("\n\n", criteriaAnalyses);
        var reportPrompt = $"""
            Unit: {birimFull} ({birim})
            Year: {yil ?? "All"}

            CRITERIA ANALYSES:
            {fullContext}

            TASK: Create a formal Self-Assessment Report in YOKAK format using the analyses provided above.
            MANDATORY RULES:
            1. STRUCTURE: ALL following headers must be present in the output:
               ## Yönetici Özeti
               ## Liderlik, Yönetişim ve Kalite
               ## Eğitim ve Öğretim
               ## Araştırma ve Geliştirme
               ## Toplumsal Katkı
               ## Güçlü Yönler
               ## Sonuç ve Öneriler
            2. DATA GAP: If data is missing for a section, write 'Bu alanda spesifik veri bulunamamıştır' but KEEP the header.
            3. FORMAT: Write headers as Markdown H2 (##).
            4. LANGUAGE: YOUR ENTIRE REPORT MUST BE IN FORMAL ACADEMIC TURKISH.
            """;

        return await _reportWriter.RunAsync(reportPrompt);
    }

    // ══════════════════════════════════════════════════════════════
    // evaluate_rubric() — Python karşılığı (İki Aşamalı: Analiz + Denetim)
    // ══════════════════════════════════════════════════════════════

    /// <summary>
    /// YÖKAK rubrik değerlendirmesi — İki aşamalı (Analiz + Denetim).
    /// Python'daki evaluate_rubric() metodunun .NET karşılığı.
    /// RubricEvaluator → RubricValidator → Birleşik rapor
    /// </summary>
    public async Task<string> EvaluateRubricAsync(IEnumerable<string> filenames)
    {
        var filenameList = filenames.ToList();
        if (!filenameList.Any()) return "Değerlendirilecek rapor seçilmedi.";

        var now = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");
        var overallResults = new List<string>
        {
            $"# Rapor Rubrik ve Denetim Raporu\n\n**Tarih:** {now}",
            $"**Değerlendirilen Raporlar:** {string.Join(", ", filenameList)}\n"
        };

        foreach (var filename in filenameList)
        {
            _logger.LogInformation("evaluate_rubric() - File: {File}", filename);

            // Tüm kriterler için bağlam topla
            var contextParts = new List<string>();
            foreach (var (cId, cDesc) in RubricCriteria)
            {
                var res = await _vectorStore.SearchAsync($"{cId} {cDesc}", k: 8, filename: filename);
                contextParts.Add($"### KRİTER: {cId}\n{res}");
            }
            var fullContext = string.Join("\n\n---\n\n", contextParts);

            // PASS 1: Analiz (RubricEvaluator)
            var analizPrompt = $"""
                ### REPORT: {filename}
                ### CONTEXT DATA:
                {fullContext}

                TASK: Perform a detailed analysis of the report according to YOKAK rubric criteria.
                FORMAT RULES:
                1. TITLE: Every criterion must have a ## header.
                2. LABELS: Provide justification and evidence in **Label:** format.
                3. SCORE: Specify the score as [PUAN: X].
                4. LANGUAGE: YOUR ENTIRE RESPONSE MUST BE IN TURKISH.

                ## [Kriter Adı]
                - **Gerekçe:** ...
                - **Kanıt:** (Quote) (Kaynak: {filename})
                - **Puan:** [PUAN: X] (1-5)
                """;
            var analizContent = await _rubricEvaluator.RunAsync(analizPrompt);

            // PASS 2: Denetim (RubricValidator)
            var denetimPrompt = $"""
                ### CONTEXT DATA:
                {fullContext}

                ### ANALYSIS RESULTS:
                {analizContent}

                TASK: Audit and compare the analysis above.
                FORMAT RULES:
                1. HEADER: Use '### 🛡️ Denetim: [Criterion Name]'.
                2. COMPARISON: If there's a difference between Analysis Score and Audit Score, explain why based on evidence.
                3. MARKER: Place the final score in [DENETİM_PUANI: X] marker.
                4. LANGUAGE: YOUR ENTIRE RESPONSE MUST BE IN TURKISH.

                ### 🛡️ Denetim: [Kriter Adı]
                - **Analiz Puanı:** [Score from analysis]
                - **Denetçi Puanı:** [Your independent score]
                - **Kıyaslama ve Gerekçe:** [Explain differences if any]
                - **Karar:** [✅ ONAYLANDI / ❌ DÜZELTİLDİ]
                Nihai Puan Marker: [DENETİM_PUANI: X]
                """;
            var denetimContent = await _rubricValidator.RunAsync(denetimPrompt);

            overallResults.Add($"""
                ## Rapor: {filename}

                ## 1. DETAYLI ANALİZLER
                {analizContent}

                ---

                ## 2. DENETÇİ VE KIYASLAMA RAPORU
                {denetimContent}
                """);
            overallResults.Add("\n---\n");
        }

        return string.Join("\n\n", overallResults);
    }

    // ══════════════════════════════════════════════════════════════
    // check_consistency() — Python karşılığı
    // ══════════════════════════════════════════════════════════════

    /// <summary>
    /// Tutarsızlık analizi.
    /// Python'daki check_consistency() metodunun .NET karşılığı.
    /// </summary>
    public async Task<string> CheckConsistencyAsync(
        string comparisonText, string? surveyText = null, string? birim = null, string? filename = null)
    {
        birim ??= DetectBirim(comparisonText);
        var searchQuery = comparisonText[..Math.Min(1000, comparisonText.Length)];
        var context = await _vectorStore.SearchAsync(searchQuery, k: 25, birim: birim, filename: filename);

        if (string.IsNullOrWhiteSpace(context))
            return "Karşılaştırma için yeterli rapor verisi bulunamadı.";

        var userClaims = surveyText != null
            ? $"### ANKET VERİLERİ:\n{surveyText}\n\n### KULLANICI BEYANLARI:\n{comparisonText}"
            : $"### KULLANICI BEYANLARI:\n{comparisonText}";

        var prompt = $"""
            ### CONSISTENCY ANALYSIS: {filename ?? birim ?? "All Reports"}
            ### 1. REPORT CONTENT (CONTEXT):
            {context}

            ### 2. CLAIMS TO VERIFY:
            {userClaims}

            TASK: Compare the claims above with the report content. For each claim, decide: [DOĞRU / YANLIŞ / BİLGİ YOK].
            RULES:
            1. Decisions must be based ONLY on the report data.
            2. LANGUAGE: YOUR ENTIRE RESPONSE MUST BE IN TURKISH.
            """;

        return await _consistencyChecker.RunAsync(prompt);
    }

    // ══════════════════════════════════════════════════════════════
    // generate_mock_data() — Python karşılığı
    // ══════════════════════════════════════════════════════════════

    /// <summary>
    /// Sentetik test verisi üretir.
    /// Python'daki generate_mock_data() metodunun .NET karşılığı.
    /// </summary>
    public async Task<string> GenerateMockDataAsync(string filename, string mode = "Tutarsız")
    {
        var context = await _vectorStore.SearchAsync("", k: 15, filename: filename);
        if (string.IsNullOrWhiteSpace(context))
            return "Veri üretmek için rapor içeriği bulunamadı.";

        var prompt = $"""
            File: {filename}
            Generation Mode: {mode}
            Report Content:
            {context[..Math.Min(10000, context.Length)]}

            TASK: Generate 2 SEPARATE blocks. Use the EXACT markers below.

            [ANKET_VERİSİ]
            (Markdown table: #, Soru, Puan (1-5), İşaretleme)

            [METİN_BEYANLARI]
            (4-6 sentences, each with [GT:DOĞRU] or [GT:YANLIŞ] tags)

            LANGUAGE: YOUR ENTIRE OUTPUT MUST BE IN TURKISH.
            """;

        var result = await _mockGenerator.RunMockAsync(prompt);

        // Validator — Python'daki output_validator.py benzeri kontrol
        if (!result.Contains("[ANKET_VERİSİ]") || !result.Contains("[METİN_BEYANLARI]"))
        {
            _logger.LogWarning("Mock output format hatası — yeniden deneniyor...");
            result = await _mockGenerator.RunMockAsync(
                prompt + "\n\nÖNEMLİ: [ANKET_VERİSİ] ve [METİN_BEYANLARI] marker'larını MUTLAKA kullan.");
        }

        return result;
    }
}
