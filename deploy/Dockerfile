# KAYRAN WEBAPP — VPS konteyner tarifi
FROM python:3.12-slim

# reportlab'ın Türkçe PDF'leri için sistem fontu + derleme temelleri
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-dejavu-core curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

# Sağlık kontrolü: Streamlit'in kendi sağlık ucu
HEALTHCHECK --interval=30s --timeout=10s --retries=5 \
    CMD curl -fs http://localhost:8501/_stcore/health || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", "--server.port=8501", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
