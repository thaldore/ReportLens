# ══════════════════════════════════════════════════════════════════
# ReportLens MAF Backend — Dockerfile
# ASP.NET Core 9.0 multi-stage build
# Port: 8080 (docker-compose.yml ile dis port 8001'e map edilir)
# ══════════════════════════════════════════════════════════════════

# Build asama
FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

# Proje kaynak kodlarini kopyala
COPY src/ src/

# Publish (Implicit restore icerir, --no-restore HATAYA SEBEP OLUYORDU)
RUN dotnet publish src/ReportLens.WebApi.csproj \
    -c Release \
    -o /app/publish

# Runtime asama
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS runtime
WORKDIR /app

# Healthcheck icin curl
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY --from=build /app/publish .

# Data dizini (volume mount point)
RUN mkdir -p /app/Data/raw_data /app/Data/processed /app/Data/test_results

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -sf http://localhost:8080/health || exit 1

ENTRYPOINT ["dotnet", "ReportLens.WebApi.dll"]
