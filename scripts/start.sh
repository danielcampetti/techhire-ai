#!/bin/bash
set -e

echo "========================================="
echo "  ComplianceAgent — Docker Setup"
echo "========================================="

# Wait for Ollama to be ready
echo "Waiting for Ollama..."
until curl -s http://ollama:11434/api/tags > /dev/null 2>&1; do
  sleep 2
done
echo "Ollama is ready."

# Pull model if not already downloaded
if ! curl -s http://ollama:11434/api/tags | grep -q "llama3"; then
  echo "Downloading llama3:8b model (4.7GB, first run only)..."
  curl -s http://ollama:11434/api/pull -d '{"name": "llama3:8b"}' | while read -r line; do
    echo "$line" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status',''), end='\r')" 2>/dev/null || true
  done
  echo -e "\nModel downloaded."
else
  echo "Model llama3:8b already available."
fi

# Initialize database
echo "Initializing database..."
python3 -c "from src.database.seed import init_db; init_db()"

# Check for PDFs and ingest if ChromaDB is empty
PDF_COUNT=$(find data/raw -name "*.pdf" 2>/dev/null | wc -l)
if [ "$PDF_COUNT" -gt 0 ]; then
  echo "Found $PDF_COUNT PDFs. Checking if ingestion needed..."
  python3 -c "
from src.ingestion.embedder import get_collection
c = get_collection()
if c.count() == 0:
    print('ChromaDB empty — running ingestion...')
    from src.api.main import ingest_documents
    import asyncio
    asyncio.run(ingest_documents())
    print('Ingestion complete.')
else:
    print(f'ChromaDB has {c.count()} chunks — skipping ingestion.')
"
else
  echo "No PDFs in data/raw/ — add PDFs and run POST /ingest manually."
fi

echo "========================================="
echo "  Server starting on http://localhost:8000"
echo "  Login: admin/admin123 or analista/analista123"
echo "========================================="

# Start the server
exec uvicorn src.api.main:app --host 0.0.0.0 --port 8000
