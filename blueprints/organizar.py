from flask import Blueprint, render_template, request, send_file
from PyPDF2 import PdfWriter
from extensions import limiter
from utils import err, validate_pdf_upload, open_pdf
import io
import logging

logger = logging.getLogger(__name__)

organizar_bp = Blueprint('organizar', __name__)


@organizar_bp.route('/unir', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def unir():
    if request.method == 'POST':
        try:
            files = request.files.getlist('pdfs')

            if not files or len(files) == 0:
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
                mimetype='application/pdf',
            )

        except Exception as e:
            logger.error(f"Unexpected error in merge: {e}")
            return err("Error inesperado al unir PDFs", 500)

    return render_template('unir.html')


@organizar_bp.route('/extraer', methods=['GET', 'POST'])
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
                mimetype='application/pdf',
            )

        except Exception as e:
            logger.error(f"Unexpected error in extraction: {e}")
            return err("Error inesperado al extraer páginas", 500)

    return render_template('extraer.html')


@organizar_bp.route('/eliminar', methods=['GET', 'POST'])
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
                mimetype='application/pdf',
            )

        except Exception as e:
            logger.error(f"Unexpected error in page deletion: {e}")
            return err("Error inesperado al eliminar páginas", 500)

    return render_template('eliminar.html')


@organizar_bp.route('/reorganizar', methods=['GET', 'POST'])
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
                mimetype='application/pdf',
            )

        except Exception as e:
            logger.error(f"Unexpected error in page reorder: {e}")
            return err("Error inesperado al reorganizar páginas", 500)

    return render_template('reorganizar.html')
