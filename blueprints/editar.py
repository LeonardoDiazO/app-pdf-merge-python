from flask import Blueprint, render_template, request, send_file
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.colors import white, black
from reportlab.pdfbase.pdfmetrics import stringWidth
from extensions import limiter
from utils import err, validate_pdf_upload, open_pdf
import io
import logging

logger = logging.getLogger(__name__)

editar_bp = Blueprint('editar', __name__)

# ── Rotar ─────────────────────────────────────────────────────────────────────

@editar_bp.route('/rotar', methods=['GET', 'POST'])
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

            stream, error = validate_pdf_upload(pdf_file, max_mb=20)
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
                mimetype='application/pdf',
            )

        except Exception as e:
            logger.error(f"Unexpected error in rotation: {e}")
            return err("Error inesperado al rotar páginas", 500)

    return render_template('rotar.html')


# ── Paginar ───────────────────────────────────────────────────────────────────

VALID_POSITIONS = {
    'top-left', 'top-center', 'top-right',
    'bottom-left', 'bottom-center', 'bottom-right',
}
VALID_FORMATS = {'number', 'page_number', 'of_total', 'classic'}
VALID_FONT_SIZES = {10, 12, 14}


def _format_page_number(number, last_number, fmt):
    return {
        'number':      str(number),
        'page_number': f'Página {number}',
        'of_total':    f'{number} / {last_number}',
        'classic':     f'- {number} -',
    }.get(fmt, str(number))


def _build_number_overlay(page_width, page_height, text, position, font_size, cover_existing, margin=28.35):
    font_name = 'Helvetica-Bold'
    text_w = stringWidth(text, font_name, font_size)
    text_h = font_size

    h_positions = {
        'left':   margin,
        'center': (page_width - text_w) / 2,
        'right':  page_width - text_w - margin,
    }
    v_positions = {
        'bottom': margin,
        'top':    page_height - margin - text_h,
    }
    v_key, h_key = position.split('-', 1)
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


@editar_bp.route('/paginar', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def paginar():
    if request.method == 'POST':
        try:
            pdf_file = request.files.get('pdf')

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

            stream, error = validate_pdf_upload(pdf_file, max_mb=20)
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
                        font_size, cover_existing,
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
                mimetype='application/pdf',
            )

        except Exception as e:
            logger.error(f"Unexpected error in pagination: {e}")
            return err("Error inesperado al paginar el PDF", 500)

    return render_template('paginar.html')
