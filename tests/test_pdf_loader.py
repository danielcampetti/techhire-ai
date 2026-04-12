"""Tests for PDF loading functionality."""
import pytest
import fitz  # PyMuPDF
from pathlib import Path

from src.ingestion.pdf_loader import load_pdf, load_all_pdfs, DocumentPage


def _make_pdf(path: Path, text: str, title: str = "") -> None:
    """Helper: create a minimal PDF with one page of text."""
    doc = fitz.open()
    if title:
        doc.set_metadata({"title": title})
    page = doc.new_page()
    page.insert_text((50, 72), text)
    doc.save(str(path))
    doc.close()


def test_load_pdf_returns_document_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "norma.pdf"
    _make_pdf(pdf_path, "Artigo 1. Esta e uma norma de compliance.")

    pages = load_pdf(pdf_path)

    assert len(pages) >= 1
    assert isinstance(pages[0], DocumentPage)
    assert pages[0].filename == "norma.pdf"
    assert pages[0].page_number == 1
    assert "compliance" in pages[0].content.lower()


def test_load_pdf_page_metadata_contains_source(tmp_path: Path) -> None:
    pdf_path = tmp_path / "circ3978.pdf"
    _make_pdf(pdf_path, "Circular BCB 3978.")

    pages = load_pdf(pdf_path)

    assert pages[0].metadata["source"] == "circ3978.pdf"
    assert pages[0].metadata["page"] == 1


def test_load_pdf_skips_empty_pages(tmp_path: Path) -> None:
    pdf_path = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()  # no text inserted
    doc.save(str(pdf_path))
    doc.close()

    pages = load_pdf(pdf_path)

    assert len(pages) == 0


def test_load_pdf_uses_filename_as_title_when_metadata_absent(tmp_path: Path) -> None:
    pdf_path = tmp_path / "resolucao338.pdf"
    _make_pdf(pdf_path, "Texto da resolucao.")

    pages = load_pdf(pdf_path)

    assert pages[0].title != ""


def test_load_all_pdfs_loads_multiple_files(tmp_path: Path) -> None:
    for name in ["doc_a.pdf", "doc_b.pdf"]:
        _make_pdf(tmp_path / name, f"Conteudo de {name}")

    pages = load_all_pdfs(tmp_path)
    filenames = {p.filename for p in pages}

    assert "doc_a.pdf" in filenames
    assert "doc_b.pdf" in filenames


def test_load_all_pdfs_empty_directory(tmp_path: Path) -> None:
    pages = load_all_pdfs(tmp_path)
    assert pages == []
