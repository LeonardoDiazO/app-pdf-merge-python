from flask import Flask, render_template, request, send_file, jsonify
from PyPDF2 import PdfReader, PdfWriter
from PyPDF2.errors import PdfReadError
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.colors import white, black
from reportlab.pdfbase.pdfmetrics import stringWidth
from PIL import Image, UnidentifiedImageError
import io
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey-change-in-production')
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

MAX_PAGES = 200


@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' https://cdnjs.cloudflare.com; "
        "worker-src blob:; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    )
    return response


def err(msg, status=400):
    """Return a structured JSON error response."""
    return jsonify({"error": msg}), status


def validate_pdf_upload(file, max_mb=10):
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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/unir', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def unir():
    if request.method == 'POST':
        try:
            files = request.files.getlist('pdfs')

            if not files or len(files) == 0:
                logger.warning("No files uploaded")
                return err("No se han subido archivos")

            if len(files) < 2:
                return err("Se necesitan al menos 2 archivos PDF para unir")

            order = request.form.get('order', '')
            if not order:
                return err("Orden de archivos no especificada")

            try:
                order_indices = list(map(int, order.split(",")))
            except ValueError as e:
                logger.error(f"Invalid order format: {e}")
                return err("Formato de orden inválido")

            uploaded_streams = []
            for i, file in enumerate(files):
                stream, error = validate_pdf_upload(file)
                if error:
                    return error
                uploaded_streams.append(stream)

            if len(order_indices) != len(uploaded_streams):
                return err("Error en la correspondencia del orden")

            try:
                ordered_streams = [uploaded_streams[i] for i in order_indices]
            except IndexError as e:
                logger.error(f"Invalid order index: {e}")
                return err("Error en la correspondencia del orden")

            writer = PdfWriter()
            for idx, stream in enumerate(ordered_streams):
                reader, error = open_pdf(stream, f"El PDF en posición {idx + 1}")
                if error:
                    return error
                for page in reader.pages:
                    writer.add_page(page)

            output_stream = io.BytesIO()
            writer.write(output_stream)
            output_stream.seek(0)

            logger.info(f"Successfully merged {len(files)} PDFs")
            return send_file(
                output_stream,
                as_attachment=True,
                download_name="merged_output.pdf",
                mimetype='application/pdf'
            )

        except Exception as e:
            logger.error(f"Unexpected error in merge: {e}")
            return err("Error inesperado al unir PDFs", 500)

    return render_template('unir.html')


@app.route('/eliminar', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def eliminar():
    if request.method == 'POST':
        try:
            pdf_file = request.files.get('pdf')
            pages_str = request.form.get('remove_pages', '')

            stream, error = validate_pdf_upload(pdf_file, max_mb=5)
            if error:
                return error

            if not pages_str:
                return err("No se especificaron páginas para eliminar")

            try:
                pages_to_remove = list(map(int, pages_str.split(',')))
            except ValueError as e:
                logger.error(f"Invalid page format: {e}")
                return err("Formato de páginas inválido")

            reader, error = open_pdf(stream, "El PDF")
            if error:
                return error

            total_pages = len(reader.pages)
            for page_idx in pages_to_remove:
                if page_idx < 0 or page_idx >= total_pages:
                    return err(f"Índice de página inválido: {page_idx}")

            writer = PdfWriter()
            pages_kept = 0
            for i, page in enumerate(reader.pages):
                if i not in pages_to_remove:
                    writer.add_page(page)
                    pages_kept += 1

            if pages_kept == 0:
                return err("No se pueden eliminar todas las páginas")

            output_stream = io.BytesIO()
            writer.write(output_stream)
            output_stream.seek(0)

            logger.info(f"Successfully removed {len(pages_to_remove)} pages from PDF")
            return send_file(
                output_stream,
                as_attachment=True,
                download_name="cleaned_output.pdf",
                mimetype='application/pdf'
            )

        except Exception as e:
            logger.error(f"Unexpected error in page deletion: {e}")
            return err("Error inesperado al eliminar páginas", 500)

    return render_template('eliminar.html')


@app.route('/rotar', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def rotar():
    if request.method == 'POST':
        try:
            pdf_file = request.files.get('pdf')
            pages_str = request.form.get('pages', '')

            try:
                rotation = int(request.form.get('rotation', '180'))
            except ValueError:
                return err("Ángulo de rotación inválido")

            if rotation not in [90, 180, 270]:
                return err("Ángulo de rotación inválido")

            stream, error = validate_pdf_upload(pdf_file, max_mb=10)
            if error:
                return error

            if not pages_str:
                return err("No se especificaron páginas para rotar")

            try:
                pages_to_rotate = set(map(int, pages_str.split(',')))
            except ValueError as e:
                logger.error(f"Invalid page format: {e}")
                return err("Formato de páginas inválido")

            reader, error = open_pdf(stream, "El PDF")
            if error:
                return error

            total_pages = len(reader.pages)
            for page_idx in pages_to_rotate:
                if page_idx < 0 or page_idx >= total_pages:
                    return err(f"Índice de página inválido: {page_idx}")

            writer = PdfWriter()
            for i, page in enumerate(reader.pages):
                if i in pages_to_rotate:
                    page.rotate(rotation)
                writer.add_page(page)

            output_stream = io.BytesIO()
            writer.write(output_stream)
            output_stream.seek(0)

            logger.info(f"Successfully rotated {len(pages_to_rotate)} pages by {rotation}°")
            return send_file(
                output_stream,
                as_attachment=True,
                download_name="rotated_output.pdf",
                mimetype='application/pdf'
            )

        except Exception as e:
            logger.error(f"Unexpected error in rotation: {e}")
            return err("Error inesperado al rotar páginas", 500)

    return render_template('rotar.html')


@app.route('/extraer', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def extraer():
    if request.method == 'POST':
        try:
            pdf_file = request.files.get('pdf')
            pages_str = request.form.get('extract_pages', '')

            stream, error = validate_pdf_upload(pdf_file, max_mb=10)
            if error:
                return error

            if not pages_str:
                return err("No se especificaron páginas para extraer")

            try:
                pages_to_extract = list(map(int, pages_str.split(',')))
            except ValueError as e:
                logger.error(f"Invalid page format: {e}")
                return err("Formato de páginas inválido")

            if len(pages_to_extract) == 0:
                return err("Debes seleccionar al menos una página")

            reader, error = open_pdf(stream, "El PDF")
            if error:
                return error

            total_pages = len(reader.pages)
            for page_idx in pages_to_extract:
                if page_idx < 0 or page_idx >= total_pages:
                    return err(f"Índice de página inválido: {page_idx}")

            writer = PdfWriter()
            for page_idx in pages_to_extract:
                writer.add_page(reader.pages[page_idx])

            output_stream = io.BytesIO()
            writer.write(output_stream)
            output_stream.seek(0)

            logger.info(f"Successfully extracted {len(pages_to_extract)} pages")
            return send_file(
                output_stream,
                as_attachment=True,
                download_name="extracted_output.pdf",
                mimetype='application/pdf'
            )

        except Exception as e:
            logger.error(f"Unexpected error in extraction: {e}")
            return err("Error inesperado al extraer páginas", 500)

    return render_template('extraer.html')


@app.route('/imagenes', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def imagenes():
    if request.method == 'POST':
        try:
            files = request.files.getlist('images')

            if not files or len(files) == 0:
                return err("No se han subido imágenes")

            MAX_IMAGES = 20
            MAX_IMAGE_MB = 10
            ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}

            if len(files) > MAX_IMAGES:
                return err(f"Máximo {MAX_IMAGES} imágenes permitidas")

            order = request.form.get('order', '')
            if not order:
                return err("Orden de imágenes no especificado")

            try:
                order_indices = list(map(int, order.split(",")))
            except ValueError:
                return err("Formato de orden inválido")

            uploaded_contents = []
            for file in files:
                if not file or not file.filename:
                    return err("Archivo inválido")
                ext = os.path.splitext(file.filename.lower())[1]
                if ext not in ALLOWED_EXTENSIONS:
                    return err(f"Formato no soportado: '{file.filename}'. Use JPG, PNG, WEBP, GIF o BMP")
                content = file.read()
                if len(content) == 0:
                    return err(f"El archivo '{file.filename}' está vacío")
                if len(content) > MAX_IMAGE_MB * 1024 * 1024:
                    return err(f"El archivo '{file.filename}' supera el límite de {MAX_IMAGE_MB} MB")
                uploaded_contents.append(content)

            if len(order_indices) != len(uploaded_contents):
                return err("Error en la correspondencia del orden")

            try:
                ordered_contents = [uploaded_contents[i] for i in order_indices]
            except IndexError:
                return err("Error en la correspondencia del orden")

            pil_images = []
            for content in ordered_contents:
                try:
                    img = Image.open(io.BytesIO(content))
                    img = img.convert('RGB')
                    pil_images.append(img)
                except UnidentifiedImageError:
                    return err("Una de las imágenes no es válida o está dañada")

            output_stream = io.BytesIO()
            if len(pil_images) == 1:
                pil_images[0].save(output_stream, format='PDF')
            else:
                pil_images[0].save(
                    output_stream,
                    format='PDF',
                    save_all=True,
                    append_images=pil_images[1:]
                )
            output_stream.seek(0)

            logger.info(f"Successfully converted {len(pil_images)} images to PDF")
            return send_file(
                output_stream,
                as_attachment=True,
                download_name="images_output.pdf",
                mimetype='application/pdf'
            )

        except Exception as e:
            logger.error(f"Unexpected error in images to PDF: {e}")
            return err("Error inesperado al convertir imágenes", 500)

    return render_template('imagenes.html')


@app.route('/reorganizar', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def reorganizar():
    if request.method == 'POST':
        try:
            pdf_file = request.files.get('pdf')
            order_str = request.form.get('page_order', '')

            stream, error = validate_pdf_upload(pdf_file, max_mb=10)
            if error:
                return error

            if not order_str:
                return err("No se especificó el nuevo orden de páginas")

            try:
                new_order = list(map(int, order_str.split(',')))
            except ValueError:
                return err("Formato de orden inválido")

            reader, error = open_pdf(stream, "El PDF")
            if error:
                return error

            total_pages = len(reader.pages)

            if len(new_order) != total_pages:
                return err(f"El orden debe incluir las {total_pages} páginas del documento")

            if sorted(new_order) != list(range(total_pages)):
                return err("El orden contiene índices de página inválidos o duplicados")

            writer = PdfWriter()
            for page_idx in new_order:
                writer.add_page(reader.pages[page_idx])

            output_stream = io.BytesIO()
            writer.write(output_stream)
            output_stream.seek(0)

            logger.info(f"Successfully reordered PDF with {total_pages} pages")
            return send_file(
                output_stream,
                as_attachment=True,
                download_name="reordered_output.pdf",
                mimetype='application/pdf'
            )

        except Exception as e:
            logger.error(f"Unexpected error in page reorder: {e}")
            return err("Error inesperado al reorganizar páginas", 500)

    return render_template('reorganizar.html')


@app.route('/info')
def info():
    return render_template('index.html')


# ── Paginación ────────────────────────────────────────────────────────────────

VALID_POSITIONS = {
    'top-left', 'top-center', 'top-right',
    'bottom-left', 'bottom-center', 'bottom-right',
}
VALID_FORMATS = {'number', 'page_number', 'of_total', 'classic'}
VALID_FONT_SIZES = {10, 12, 14}


def _format_page_number(number, last_number, fmt):
    """Format the page number string according to the chosen style."""
    return {
        'number':      str(number),
        'page_number': f'Página {number}',
        'of_total':    f'{number} / {last_number}',
        'classic':     f'- {number} -',
    }.get(fmt, str(number))


def _build_number_overlay(page_width, page_height, text, position, font_size, cover_existing, margin=28.35):
    """
    Create a single-page PDF (BytesIO) containing only the page number text.
    margin is in PDF points (1 cm ≈ 28.35 pt).
    """
    font_name = 'Helvetica-Bold'
    text_w = stringWidth(text, font_name, font_size)
    text_h = font_size  # approximate glyph height

    # Calculate (x, y) — ReportLab origin is bottom-left
    h_positions = {
        'left':   margin,
        'center': (page_width - text_w) / 2,
        'right':  page_width - text_w - margin,
    }
    v_positions = {
        'bottom': margin,
        'top':    page_height - margin - text_h,
    }
    v_key, h_key = position.split('-', 1)  # e.g. 'bottom-center' → ('bottom', 'center')
    x = h_positions[h_key]
    y = v_positions[v_key]

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(page_width, page_height))

    if cover_existing:
        pad = 4
        c.setFillColor(white)
        c.rect(x - pad, y - pad, text_w + pad * 2, text_h + pad * 2, fill=1, stroke=0)

    c.setFillColor(black)
    c.setFont(font_name, font_size)
    c.drawString(x, y, text)
    c.save()

    buf.seek(0)
    return PdfReader(buf)


@app.route('/paginar', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def paginar():
    if request.method == 'POST':
        try:
            pdf_file = request.files.get('pdf')

            # Parse & validate params
            try:
                start_number = int(request.form.get('start_number', 1))
                from_page    = int(request.form.get('from_page', 1))
                font_size    = int(request.form.get('font_size', 12))
            except ValueError:
                return err("Parámetros numéricos inválidos")

            position       = request.form.get('position', 'bottom-center')
            fmt            = request.form.get('format', 'number')
            cover_existing = request.form.get('cover_existing') == 'true'

            if position not in VALID_POSITIONS:
                return err("Posición inválida")
            if fmt not in VALID_FORMATS:
                return err("Formato inválido")
            if font_size not in VALID_FONT_SIZES:
                return err("Tamaño de fuente inválido")
            if start_number < 1:
                return err("El número inicial debe ser mayor que 0")

            stream, error = validate_pdf_upload(pdf_file, max_mb=10)
            if error:
                return error

            reader, error = open_pdf(stream, "El PDF")
            if error:
                return error

            total_pages = len(reader.pages)

            if from_page < 1 or from_page > total_pages:
                return err(f"La página de inicio debe estar entre 1 y {total_pages}")

            total_numbered = total_pages - (from_page - 1)
            last_number    = start_number + total_numbered - 1

            writer = PdfWriter()
            page_number = start_number

            for i, page in enumerate(reader.pages):
                page_1based = i + 1

                if page_1based < from_page:
                    writer.add_page(page)
                    continue

                page_width  = float(page.mediabox.width)
                page_height = float(page.mediabox.height)

                text = _format_page_number(page_number, last_number, fmt)

                try:
                    overlay_reader = _build_number_overlay(
                        page_width, page_height, text, position,
                        font_size, cover_existing
                    )
                    page.merge_page(overlay_reader.pages[0])
                except Exception as e:
                    logger.error(f"Error building overlay for page {page_1based}: {e}")
                    return err(f"Error al procesar la página {page_1based}")

                writer.add_page(page)
                page_number += 1

            output_stream = io.BytesIO()
            writer.write(output_stream)
            output_stream.seek(0)

            logger.info(
                f"Paginated PDF: {total_pages} pages, "
                f"numbering from page {from_page} starting at {start_number}"
            )
            return send_file(
                output_stream,
                as_attachment=True,
                download_name='paginated_output.pdf',
                mimetype='application/pdf'
            )

        except Exception as e:
            logger.error(f"Unexpected error in pagination: {e}")
            return err("Error inesperado al paginar el PDF", 500)

    return render_template('paginar.html')


if __name__ == '__main__':
    app.run(debug=True)
