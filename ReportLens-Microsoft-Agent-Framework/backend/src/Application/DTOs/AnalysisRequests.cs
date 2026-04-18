// ══════════════════════════════════════════════════════════════════
// ReportLens MAF Backend — Application DTOs
// Tüm Request/Response modelleri Clean Architecture prensibine uygun
// Application katmanında tanımlanmıştır.
// ══════════════════════════════════════════════════════════════════

namespace ReportLens.Application.DTOs;

// ── Requests ─────────────────────────────────────────────────────

public record AnalyzeRequest(
    string Query,
    string? Birim = null,
    string? Yil = null
);

public record SingleReportRequest(string Filename);

public record SelfEvalRequest(
    string Birim,
    string? Yil = null
);

public record RubricRequest(List<string> Filenames);

public record ConsistencyRequest(
    string ComparisonText,
    string? SurveyText = null,
    string? Birim = null,
    string? Filename = null
);

public record MockDataRequest(
    string Filename,
    string Mode = "Tutarsız"
);

public record ProcessRequest(bool ForceReindex = false);

// ── Responses ────────────────────────────────────────────────────

public record AnalysisResponse(
    string Result,
    string? AutoBirim = null,
    string? AutoYil = null
);

public record ReportListResponse(List<ReportItem> Reports);

public record ReportItem(
    string Filename,
    string Birim,
    string Yil,
    string Tur,
    double SizeKb
);

public record RawFileItem(
    string Filename,
    string Birim,
    string Yil,
    string Tur,
    double SizeMb,
    bool Processed
);

public record StatusResponse(
    string Durum,
    int HamRaporSayisi,
    int IslenmiRaporSayisi,
    int VektorSayisi,
    string Model,
    string EmbeddingModel,
    string OllamaUrl,
    string MssqlHost,
    string MssqlDb,
    string TableName,
    string Environment,
    string Framework
);
