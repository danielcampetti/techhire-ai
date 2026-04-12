"""Text chunking utilities for compliance documents.

Splits extracted PDF pages into overlapping semantic chunks using
LangChain's RecursiveCharacterTextSplitter with regulatory-document-aware
separators (sections/articles, then paragraphs, then sentences).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.ingestion.pdf_loader import DocumentPage


@dataclass
class TextChunk:
    """A semantic chunk of text with source provenance."""

    content: str
    filename: str
    page_number: int
    title: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)


def chunk_pages(
    pages: List[DocumentPage],
    chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> List[TextChunk]:
    """Split document pages into overlapping text chunks.

    Uses hierarchical separators suited for regulatory documents:
    section breaks -> paragraph breaks -> newlines -> sentences -> words.

    Args:
        pages: List of DocumentPage objects to chunk.
        chunk_size: Target maximum characters per chunk.
        chunk_overlap: Number of overlapping characters between adjacent chunks.

    Returns:
        List of TextChunk objects preserving source metadata.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n\n", "\n\n", "\n", ". ", " ", ""],
        length_function=len,
    )

    chunks: List[TextChunk] = []
    for page in pages:
        texts = splitter.split_text(page.content)
        for i, text in enumerate(texts):
            if not text.strip():
                continue
            chunks.append(
                TextChunk(
                    content=text,
                    filename=page.filename,
                    page_number=page.page_number,
                    title=page.title,
                    chunk_index=i,
                    metadata={
                        **page.metadata,
                        "chunk_index": i,
                    },
                )
            )

    return chunks
