"""Resume text extraction utilities.

Provides a single public function, `extract_text`, that accepts raw file bytes
and a file extension and returns the plain text content of the document.

Supported formats:
    pdf   — via PyMuPDF (fitz).  Text-layer PDFs only; scanned/image PDFs
             that have no text layer will raise ExtractionError.
    docx  — via python-docx.  Reads all paragraph text in document order.

Raises:
    ExtractionError — for any condition that makes the document unreadable or
                      unusable as resume text:
                          - corrupt / truncated file
                          - password-protected (encrypted) PDF
                          - PDF with no extractable text (scanned / image-only)
                          - empty DOCX (no paragraphs with text)
                          - unsupported extension
"""

import io

import fitz  # PyMuPDF
from docx import Document
from docx.opc.exceptions import PackageNotFoundError


class ExtractionError(ValueError):
    """Raised when text cannot be extracted from an uploaded resume file.

    Inherits from ValueError so callers can catch it without importing
    this module just for the exception type, but it is also importable
    directly for explicit handling.
    """


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_text(file_bytes: bytes, ext: str) -> str:
    """Extract plain text from a PDF or DOCX resume.

    Args:
        file_bytes: Raw bytes of the uploaded file.
        ext:        Lowercase extension without dot — ``"pdf"`` or ``"docx"``.

    Returns:
        Non-empty string containing the extracted text, with pages/sections
        separated by newlines and excess whitespace normalised.

    Raises:
        ExtractionError: If the document is corrupt, encrypted, blank,
                         or uses an unsupported format.
    """
    ext = ext.lower()
    if ext == "pdf":
        return _extract_pdf(file_bytes)
    if ext == "docx":
        return _extract_docx(file_bytes)
    raise ExtractionError(
        f"Unsupported extension '{ext}'. Only 'pdf' and 'docx' are supported."
    )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extract_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF using PyMuPDF.

    Password-protected PDFs and PDFs with no text layer (scanned / image-only)
    are both treated as unreadable and raise ExtractionError.
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as exc:
        raise ExtractionError(f"Could not open PDF: {exc}") from exc

    try:
        # needs_pass is non-zero when the document requires a password.
        if doc.needs_pass:
            raise ExtractionError(
                "This PDF is password-protected. "
                "Please upload an unlocked version of your resume."
            )

        pages_text: list[str] = []
        for page in doc:
            page_text = page.get_text()
            stripped = page_text.strip()
            if stripped:
                pages_text.append(stripped)

        if not pages_text:
            raise ExtractionError(
                "No text could be extracted from this PDF. "
                "It may be a scanned image or contain only non-text content. "
                "Please upload a text-based PDF or a DOCX version of your resume."
            )

        return "\n\n".join(pages_text)

    finally:
        doc.close()


def _extract_docx(file_bytes: bytes) -> str:
    """Extract text from a DOCX file using python-docx.

    Reads all paragraph text in document order and joins non-empty paragraphs
    with newlines.  Raises ExtractionError for corrupt files or empty documents.
    """
    try:
        doc = Document(io.BytesIO(file_bytes))
    except PackageNotFoundError as exc:
        raise ExtractionError(f"Could not open DOCX: file is corrupt or not a valid DOCX.") from exc
    except Exception as exc:
        raise ExtractionError(f"Could not open DOCX: {exc}") from exc

    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    if not paragraphs:
        raise ExtractionError(
            "No text could be extracted from this DOCX file. "
            "The document appears to be empty."
        )

    return "\n".join(paragraphs)
