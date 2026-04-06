from flask import jsonify
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
import io
import logging

logger = logging.getLogger(__name__)

MAX_PAGES = 200


def err(msg, status=400):
    """Return a structured JSON error response."""
    return jsonify({"error": msg}), status


def validate_pdf_upload(file, max_mb=40):
    """Validate an uploaded PDF file. Returns (BytesIO, None) or (None, error_response)."""
    if not file or not file.filename:
        return None, err("Falta el archivo PDF")
    if not file.filename.lower().endswith('.pdf'):
        return None, err(f"El archivo '{file.filename}' no es un PDF válido")
    if file.mimetype != 'application/pdf':
        return None, err(f"El archivo '{file.filename}' no tiene el tipo MIME correcto")
    content = file.read()
    if len(content) == 0:
        return None, err(f"El archivo '{file.filename}' está vacío")
    if len(content) > max_mb * 1024 * 1024:
        return None, err(f"El archivo supera el límite de {max_mb} MB")
    return io.BytesIO(content), None


def open_pdf(stream, label="El PDF"):
    """Open a PdfReader safely. Returns (reader, None) or (None, error_response)."""
    try:
        stream.seek(0)
        reader = PdfReader(stream)
        if reader.is_encrypted:
            return None, err(f"{label} está protegido con contraseña")
        if len(reader.pages) == 0:
            return None, err(f"{label} no tiene páginas")
        if len(reader.pages) > MAX_PAGES:
            return None, err(f"{label} tiene demasiadas páginas (máximo {MAX_PAGES})")
        return reader, None
    except PdfReadError as e:
        logger.error(f"PdfReadError ({label}): {e}")
        return None, err(f"{label} está dañado o no se puede leer")
