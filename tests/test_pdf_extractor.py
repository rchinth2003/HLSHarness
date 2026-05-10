"""Unit tests for PdfExtractor — no Azure credentials required."""

from __future__ import annotations

from pathlib import Path

import pytest

from hlsharness.pdf_extractor import PdfExtractor

# ── helpers ───────────────────────────────────────────────────────────────────


def _minimal_pdf_bytes() -> bytes:
    """Return a valid minimal PDF binary (no text content — blank page)."""
    body = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
    )
    xref_pos = len(body)
    offsets = [9, 58, 115]
    xref = (
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        + f"{offsets[0]:010d} 00000 n \n".encode()
        + f"{offsets[1]:010d} 00000 n \n".encode()
        + f"{offsets[2]:010d} 00000 n \n".encode()
        + f"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF".encode()
    )
    return body + xref


# ── tests ─────────────────────────────────────────────────────────────────────


def test_txt_file_returns_content(tmp_path: Path) -> None:
    txt = tmp_path / "spec.txt"
    txt.write_text("agent description here", encoding="utf-8")
    result = PdfExtractor().extract(txt)
    assert result == "agent description here"


def test_yaml_file_passes_through(tmp_path: Path) -> None:
    yml = tmp_path / "spec.yaml"
    yml.write_text("openapi: 3.0.0\ninfo:\n  title: Test\n", encoding="utf-8")
    result = PdfExtractor().extract(yml)
    assert "openapi" in result


def test_json_file_passes_through(tmp_path: Path) -> None:
    js = tmp_path / "spec.json"
    js.write_text('{"openapi": "3.0.0"}', encoding="utf-8")
    result = PdfExtractor().extract(js)
    assert "openapi" in result


def test_pdf_file_returns_str(tmp_path: Path) -> None:
    pdf = tmp_path / "spec.pdf"
    pdf.write_bytes(_minimal_pdf_bytes())
    result = PdfExtractor().extract(pdf)
    assert isinstance(result, str)


def test_pdf_extension_case_insensitive(tmp_path: Path) -> None:
    pdf = tmp_path / "spec.PDF"
    pdf.write_bytes(_minimal_pdf_bytes())
    result = PdfExtractor().extract(pdf)
    assert isinstance(result, str)


def test_missing_txt_file_raises_os_error(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        PdfExtractor().extract(tmp_path / "nonexistent.txt")


def test_missing_pdf_file_raises_error(tmp_path: Path) -> None:
    # pypdf raises PdfStreamError or FileNotFoundError depending on version
    with pytest.raises((OSError, Exception)):  # noqa: B017
        PdfExtractor().extract(tmp_path / "nonexistent.pdf")
