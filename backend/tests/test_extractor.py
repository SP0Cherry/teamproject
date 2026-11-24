"""Tests for document text extraction branches (AI-01, TEST-05).

Pure-function tests: real temp files for txt; PdfReader / Document / PIL.Image
are monkeypatched to avoid binary fixtures and external native lib quirks.
"""

import pytest
from PIL import Image as PILImage

from app.core.config import settings
from app.services import extractor as ext


def test_extract_txt_happy_truncation_and_errors(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hello world", encoding="utf-8")
    text, err = ext.extract_text(str(f), "text/plain")
    assert text == "hello world"
    assert err == ""

    big = tmp_path / "big.txt"
    big.write_text("x" * (settings.max_text_chars + 50), encoding="utf-8")
    text, err = ext.extract_text(str(big), "text/plain")
    assert err == ""
    assert len(text) == settings.max_text_chars  # truncated to the cap

    empty = tmp_path / "empty.txt"
    empty.write_text("   \n  ", encoding="utf-8")
    text, err = ext.extract_text(str(empty), "text/plain")
    assert text == ""
    assert "empty text" in err

    text, err = ext.extract_text(str(tmp_path / "nope.txt"), "text/plain")
    assert text == ""
    assert "read error" in err


def test_extract_unsupported_type(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2", encoding="utf-8")
    text, err = ext.extract_text(str(f), "text/csv")
    assert text == ""
    assert "unsupported type" in err


class _FakePage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


def test_extract_pdf_branches(monkeypatch, tmp_path):
    f = tmp_path / "doc.pdf"
    f.write_bytes(b"%PDF-1.4 fake")

    class _Reader:
        def __init__(self, path):
            self.pages = [_FakePage("page one"), _FakePage("page two")]

    monkeypatch.setattr(ext, "PdfReader", _Reader)
    text, err = ext.extract_text(str(f), "application/pdf")
    assert err == ""
    assert "page one" in text and "page two" in text

    class _BigReader:
        def __init__(self, path):
            self.pages = [_FakePage("x")] * (settings.max_pdf_pages + 1)

    monkeypatch.setattr(ext, "PdfReader", _BigReader)
    text, err = ext.extract_text(str(f), "application/pdf")
    assert text == ""
    assert "exceeds" in err and str(settings.max_pdf_pages) in err

    class _BoomReader:
        def __init__(self, path):
            raise RuntimeError("boom")

    monkeypatch.setattr(ext, "PdfReader", _BoomReader)
    text, err = ext.extract_text(str(f), "application/pdf")
    assert text == ""
    assert "pdf parse error" in err

    class _EmptyReader:
        def __init__(self, path):
            self.pages = [_FakePage(""), _FakePage("   ")]

    monkeypatch.setattr(ext, "PdfReader", _EmptyReader)
    text, err = ext.extract_text(str(f), "application/pdf")
    assert text == ""
    assert "no extractable text" in err


class _FakePara:
    def __init__(self, t):
        self.text = t


def test_extract_docx_branches(monkeypatch, tmp_path):
    f = tmp_path / "d.docx"
    f.write_bytes(b"fake")
    mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    class _Doc:
        def __init__(self, path):
            self.paragraphs = [_FakePara("hello"), _FakePara("docx")]

    monkeypatch.setattr(ext, "Document", _Doc)
    text, err = ext.extract_text(str(f), mime)
    assert err == ""
    assert "hello" in text and "docx" in text

    class _BoomDoc:
        def __init__(self, path):
            raise RuntimeError("boom")

    monkeypatch.setattr(ext, "Document", _BoomDoc)
    text, err = ext.extract_text(str(f), mime)
    assert text == ""
    assert "docx parse error" in err

    class _EmptyDoc:
        def __init__(self, path):
            self.paragraphs = [_FakePara(""), _FakePara(" ")]

    monkeypatch.setattr(ext, "Document", _EmptyDoc)
    text, err = ext.extract_text(str(f), mime)
    assert text == ""
    assert "empty docx" in err


class _FakeImg:
    def __init__(self, size):
        self._size = size

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    @property
    def size(self):
        return self._size


def _raise(exc):
    def _fn(*a, **k):
        raise exc

    return _fn


def test_extract_image_branches(monkeypatch, tmp_path):
    f = tmp_path / "img.png"
    f.write_bytes(b"\x89PNG fake")

    # ocr not configured
    text, err = ext.extract_text(str(f), "image/png", ocr_fn=None)
    assert text == ""
    assert "ocr not configured" in err

    # image too large
    monkeypatch.setattr(
        PILImage, "open", lambda p: _FakeImg((settings.max_image_pixels + 1, 1))
    )
    text, err = ext.extract_text(str(f), "image/png", ocr_fn=lambda p: "x")
    assert text == ""
    assert "exceeds" in err

    # image parse error
    monkeypatch.setattr(PILImage, "open", _raise(RuntimeError("boom")))
    text, err = ext.extract_text(str(f), "image/png", ocr_fn=lambda p: "x")
    assert text == ""
    assert "image parse error" in err

    # small image, happy ocr
    monkeypatch.setattr(PILImage, "open", lambda p: _FakeImg((10, 10)))
    text, err = ext.extract_text(str(f), "image/png", ocr_fn=lambda p: "extracted text")
    assert err == ""
    assert text == "extracted text"

    # ocr raises
    text, err = ext.extract_text(str(f), "image/png", ocr_fn=_raise(RuntimeError("ocr")))
    assert text == ""
    assert "ocr error" in err

    # ocr returns only whitespace
    text, err = ext.extract_text(str(f), "image/png", ocr_fn=lambda p: "   \n ")
    assert text == ""
    assert "ocr returned no text" in err
