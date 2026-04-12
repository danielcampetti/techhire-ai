"""PDF loading utilities using PyMuPDF (fitz).

Extracts text page-by-page from PDF documents, returning structured
DocumentPage objects with content and source metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

import fitz  # PyMuPDF


@dataclass
class DocumentPage:
    """A single page extracted from a PDF document."""

    content: str
    filename: str
    page_number: int
    title: str
    metadata: dict = field(default_factory=dict)


def load_pdf(path: Path) -> List[DocumentPage]:
    """Extract all non-empty pages from a PDF file.

    Args:
        path: Absolute or relative path to the PDF file.

    Returns:
        List of DocumentPage objects, one per non-empty page.
    """
    doc = fitz.open(str(path))
    raw_title: str = doc.metadata.get("title", "").strip()
    title: str = raw_title if raw_title else path.stem

    pages: List[DocumentPage] = []
    for page_num, page in enumerate(doc):
        text = page.get_text()
        if not text.strip():
            continue
        pages.append(
            DocumentPage(
                content=text,
                filename=path.name,
                page_number=page_num + 1,
                title=title,
                metadata={
                    "source": path.name,
                    "page": page_num + 1,
                    "title": title,
                },
            )
        )

    doc.close()
    return pages


def load_all_pdfs(directory: Path) -> List[DocumentPage]:
    """Load all PDF files found in the given directory.

    Args:
        directory: Path to the directory containing PDF files.

    Returns:
        Concatenated list of DocumentPage objects from all PDFs.
    """
    pages: List[DocumentPage] = []
    for pdf_path in sorted(directory.glob("*.pdf")):
        pages.extend(load_pdf(pdf_path))
    return pages
