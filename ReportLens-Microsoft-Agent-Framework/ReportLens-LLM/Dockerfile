# ══════════════════════════════════════════════════════════════════
# ReportLens MAF LLM Microservice — Dockerfile
# ASP.NET Core 9 + Semantic Kernel
# ══════════════════════════════════════════════════════════════════

FROM mcr.microsoft.com/dotnet/sdk:9.0 AS build
WORKDIR /src

# Kalan dosyaları kopyala ve publish et
COPY src/ ReportLens.LLM/
WORKDIR "/src/ReportLens.LLM"
RUN dotnet publish "ReportLens.LLM.csproj" -c Release -o /app/publish

# Runtime imajı
FROM mcr.microsoft.com/dotnet/aspnet:9.0 AS final
WORKDIR /app
COPY --from=build /app/publish .

# Port
ENV ASPNETCORE_URLS=http://+:8080
EXPOSE 8080

ENTRYPOINT ["dotnet", "ReportLens.LLM.dll"]
