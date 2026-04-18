#!/bin/bash
set -e

OLLAMA_URL="${OLLAMA_BASE_URL:-http://reportlens-ollama:11434}"

echo "=== Ollama servisi bekleniyor ($OLLAMA_URL) ==="
MAX_RETRIES=60
RETRY_COUNT=0
until curl -sf "$OLLAMA_URL/" > /dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
        echo "HATA: Ollama servisine baglanamadi."
        exit 1
    fi
    echo "  Bekleniyor... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 3
done
echo "=== Ollama hazir ==="

# Modelleri SIRAYLA indir (FastAPI baslamadan once hazir olmali)
echo "=== nomic-embed-text indiriliyor ==="
curl -sf "$OLLAMA_URL/api/pull" -d '{"name": "nomic-embed-text", "stream": false}' --max-time 600
echo ""
echo "=== nomic-embed-text hazir ==="

echo "=== llama3.1:8b indiriliyor ==="
curl -sf "$OLLAMA_URL/api/pull" -d '{"name": "llama3.1:8b", "stream": false}' --max-time 3600
echo ""
echo "=== llama3.1:8b hazir ==="

echo "=== Tum modeller hazir, ReportLens baslatiliyor ==="

echo "--------------------------------------------------------"
echo "REPORTLENS SERVISLERI HAZIR!"
echo "--------------------------------------------------------"
echo "Frontend / API:    http://localhost:8000"
echo "API Dokümantasyonu: http://localhost:8000/docs"
echo "Veritabanı (Adminer): http://localhost:8080"
echo "Ollama API:        http://localhost:11434"
echo "--------------------------------------------------------"

exec "$@"
