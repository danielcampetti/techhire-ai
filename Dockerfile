FROM python:3.11-slim

WORKDIR /app

# System deps for bcrypt and sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc && \
    rm -rf /var/lib/apt/lists/*

# Install Python deps (cached layer — only rebuilds when requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code (this layer rebuilds on any code change)
COPY . .

# Copy startup script
COPY scripts/start.sh /app/scripts/start.sh
RUN chmod +x /app/scripts/start.sh

# Create data directories
RUN mkdir -p data/raw chroma_db

EXPOSE 8000

CMD ["/app/scripts/start.sh"]
