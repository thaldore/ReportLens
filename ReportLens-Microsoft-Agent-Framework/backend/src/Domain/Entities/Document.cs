namespace ReportLens.Domain.Entities;

/// <summary>
/// Analiz edilen rapor dokümanı (Entity).
/// </summary>
public class Document
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public string FileName { get; set; } = string.Empty;
    public string Birim { get; set; } = string.Empty;
    public string? Yil { get; set; }
    public string? Tur { get; set; }
    public string Content { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime? ProcessedAt { get; set; }
    public bool IsProcessed { get; set; }
}

/// <summary>
/// Analiz sonucu (Entity).
/// </summary>
public class AnalysisResult
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid DocumentId { get; set; }
    public string AnalysisType { get; set; } = string.Empty; // "quality", "rubric", "consistency", "self-eval"
    public string Result { get; set; } = string.Empty;
    public string? Birim { get; set; }
    public string? Yil { get; set; }
    public double DurationSeconds { get; set; }
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public Document? Document { get; set; }
}

/// <summary>
/// Rubrik puanlama sonucu (Value Object).
/// </summary>
public class RubricScore
{
    public Guid Id { get; set; } = Guid.NewGuid();
    public Guid AnalysisResultId { get; set; }
    public string CriterionName { get; set; } = string.Empty;
    public int Score { get; set; } // 1-5
    public string Justification { get; set; } = string.Empty;
}
