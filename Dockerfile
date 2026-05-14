FROM python:3.11-slim

# Install curl (needed for the Ollama installer)
RUN apt-get update && apt-get install -y --no-install-recommends curl zstd && \
    rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY start.sh /start.sh
RUN chmod +x /start.sh

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

CMD ["/start.sh"]
