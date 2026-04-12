"""FastAPI application for ComplianceAgent.

Endpoints:
- GET  /         -- Chat UI (browser interface)
- POST /ingest   -- Index all PDFs in data/raw/
- POST /chat     -- Answer a regulatory question with source citations
- GET  /documents -- List all indexed documents
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Union

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"

from src.config import settings
from src.ingestion.chunker import chunk_pages
from src.ingestion.embedder import _get_client as _get_chroma_client
from src.ingestion.embedder import index_chunks, list_indexed_documents
from src.ingestion.pdf_loader import load_all_pdfs
from src.llm.ollama_client import generate
from src.retrieval.prompt_builder import build_prompt
from src.retrieval.query_engine import retrieve

app = FastAPI(
    title="ComplianceAgent API",
    description="Sistema RAG para compliance e regulamentacao financeira brasileira",
    version="1.0.0",
)


# -- Request / Response models -----------------------------------------------

class ChatRequest(BaseModel):
    pergunta: str


class FonteSchema(BaseModel):
    arquivo: str
    pagina: Union[int, str]
    score: float


class ChatResponse(BaseModel):
    resposta: str
    fontes: List[FonteSchema]


# -- Endpoints ----------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def chat_ui() -> HTMLResponse:
    """Serve the browser chat interface."""
    return HTMLResponse(_TEMPLATE_PATH.read_text(encoding="utf-8"))


@app.post("/ingest", summary="Indexar documentos PDF")
async def ingest() -> dict:
    """Processa todos os PDFs em data/raw/ e indexa seus chunks no ChromaDB.

    Returns:
        Dict com contagem de paginas processadas e chunks indexados.
    """
    raw_dir = Path(settings.data_raw_dir)
    if not raw_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Diretorio '{raw_dir}' nao encontrado. Crie-o e adicione PDFs.",
        )

    pages = load_all_pdfs(raw_dir)
    if not pages:
        return {
            "mensagem": "Nenhum PDF encontrado em data/raw/",
            "paginas_processadas": 0,
            "chunks_indexados": 0,
        }

    chunks = chunk_pages(pages, settings.chunk_size, settings.chunk_overlap)
    count = index_chunks(chunks)

    return {
        "mensagem": "Indexacao concluida com sucesso.",
        "paginas_processadas": len(pages),
        "chunks_indexados": count,
    }


@app.post("/chat", response_model=ChatResponse, summary="Consultar base regulatoria")
async def chat(request: ChatRequest) -> ChatResponse:
    """Recebe uma pergunta e retorna resposta com citacoes das fontes.

    Args:
        request: JSON body com campo `pergunta`.

    Returns:
        Resposta gerada pelo LLM e lista de fontes utilizadas.
    """
    chunks = retrieve(request.pergunta)

    if not chunks:
        return ChatResponse(
            resposta="Esta informacao nao foi encontrada nos documentos disponiveis.",
            fontes=[],
        )

    prompt = build_prompt(request.pergunta, chunks)
    resposta = await generate(prompt)

    fontes = [
        FonteSchema(
            arquivo=str(c.metadata.get("source", "desconhecido")),
            pagina=c.metadata.get("page", "?"),
            score=round(c.score, 4),
        )
        for c in chunks
    ]

    return ChatResponse(resposta=resposta, fontes=fontes)


@app.get("/documents", summary="Listar documentos indexados")
async def list_documents() -> dict:
    """Lista todos os documentos unicos presentes no indice vetorial.

    Returns:
        Dict com lista de documentos e contagem total.
    """
    client = _get_chroma_client()
    docs = list_indexed_documents(client)
    return {"documentos": docs, "total": len(docs)}
