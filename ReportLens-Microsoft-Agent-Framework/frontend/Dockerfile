# ══════════════════════════════════════════════════════════════════
# ReportLens MAF Frontend — Dockerfile
# Nginx ile statik HTML/CSS/JS servisi
# Port: 80 (docker-compose.yml ile dış port 3001'e map edilir)
# ══════════════════════════════════════════════════════════════════

FROM nginx:alpine
WORKDIR /usr/share/nginx/html

# Tüm frontend dosyalarını kopyala
COPY index.html .
COPY css/ css/
COPY js/ js/

# Nginx konfigürasyonu
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost/ || exit 1
