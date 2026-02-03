from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify
from PyPDF2 import PdfReader, PdfWriter
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import io
import logging
import os

# Configure logging
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

@app.route('/')
def index():
    return render_template('index.html')  # Página informativa

@app.route('/unir', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def unir():
    if request.method == 'POST':
        try:
            files = request.files.getlist('pdfs')
            
            # Validate files exist
            if not files or len(files) == 0:
                logger.warning("No files uploaded")
                return "No se han subido archivos", 400
            
            if len(files) < 2:
                logger.warning(f"Only {len(files)} file(s) uploaded")
                return "Se necesitan al menos 2 archivos PDF para unir", 400
            
            # Get order
            order = request.form.get('order', '')
            if not order:
                logger.warning("No order specified")
                return "Orden de archivos no especificada", 400

            try:
                order_indices = list(map(int, order.split(",")))
            except ValueError as e:
                logger.error(f"Invalid order format: {e}")
                return "Formato de orden inválido", 400

            # Validate and read files
            uploaded_files = []
            for i, file in enumerate(files):
                if not file or not file.filename:
                    logger.warning(f"Empty file at index {i}")
                    return f"Archivo vacío en posición {i+1}", 400
                
                if not file.filename.lower().endswith('.pdf'):
                    logger.warning(f"Invalid file extension: {file.filename}")
                    return f"El archivo '{file.filename}' no es un PDF válido", 400
                
                if file.mimetype != 'application/pdf':
                    logger.warning(f"Invalid MIME type for {file.filename}: {file.mimetype}")
                    return f"El archivo '{file.filename}' no tiene el tipo MIME correcto", 400
                
                file_content = file.read()
                if len(file_content) == 0:
                    logger.warning(f"Empty file content: {file.filename}")
                    return f"El archivo '{file.filename}' está vacío", 400
                
                uploaded_files.append(io.BytesIO(file_content))

            # Validate order indices
            if len(order_indices) != len(uploaded_files):
                logger.error(f"Order length mismatch: {len(order_indices)} vs {len(uploaded_files)}")
                return "Error en la correspondencia del orden", 400

            try:
                ordered_files = [uploaded_files[i] for i in order_indices]
            except IndexError as e:
                logger.error(f"Invalid order index: {e}")
                return "Error en la correspondencia del orden", 400

            # Merge PDFs
            writer = PdfWriter()
            for idx, f in enumerate(ordered_files):
                try:
                    f.seek(0)
                    reader = PdfReader(f)
                    
                    if len(reader.pages) == 0:
                        logger.warning(f"PDF at position {idx} has no pages")
                        return f"El PDF en posición {idx+1} no tiene páginas", 400
                    
                    for page in reader.pages:
                        writer.add_page(page)
                except Exception as e:
                    logger.error(f"Error reading PDF at position {idx}: {e}")
                    return f"Error al leer el PDF en posición {idx+1}: {str(e)}", 400

            # Write output
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
            return f"Error inesperado al unir PDFs: {str(e)}", 500

    return render_template('unir.html')

@app.route('/eliminar', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def eliminar():
    if request.method == 'POST':
        try:
            pdf_file = request.files.get('pdf')
            pages_str = request.form.get('remove_pages', '')
            
            if not pdf_file:
                logger.warning("No PDF file uploaded for deletion")
                return "Falta el archivo PDF", 400
            
            if not pages_str:
                logger.warning("No pages specified for deletion")
                return "No se especificaron páginas para eliminar", 400

            try:
                pages_to_remove = list(map(int, pages_str.split(',')))
            except ValueError as e:
                logger.error(f"Invalid page format: {e}")
                return "Formato de páginas inválido", 400

            if not pdf_file.filename.lower().endswith('.pdf'):
                logger.warning(f"Invalid file extension: {pdf_file.filename}")
                return "El archivo no es un PDF válido", 400
            
            if pdf_file.mimetype != 'application/pdf':
                logger.warning(f"Invalid MIME type: {pdf_file.mimetype}")
                return "El archivo no tiene el tipo MIME correcto", 400
            
            file_content = pdf_file.read()
            if len(file_content) > 5 * 1024 * 1024:
                logger.warning(f"File too large: {len(file_content)} bytes")
                return "Archivo demasiado grande (máximo 5 MB)", 400
            
            pdf_file = io.BytesIO(file_content)
            pdf_file.seek(0)

            reader = PdfReader(pdf_file)
            total_pages = len(reader.pages)
            
            if total_pages == 0:
                logger.warning("PDF has no pages")
                return "El PDF no tiene páginas", 400
            
            # Validate page indices
            for page_idx in pages_to_remove:
                if page_idx < 0 or page_idx >= total_pages:
                    logger.warning(f"Invalid page index: {page_idx}")
                    return f"Índice de página inválido: {page_idx}", 400
            
            writer = PdfWriter()
            pages_kept = 0
            
            for i, page in enumerate(reader.pages):
                if i not in pages_to_remove:
                    writer.add_page(page)
                    pages_kept += 1
            
            if pages_kept == 0:
                logger.warning("All pages would be removed")
                return "No se pueden eliminar todas las páginas", 400

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
            return f"Error inesperado al eliminar páginas: {str(e)}", 500

    return render_template('eliminar.html')

@app.route('/rotar', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def rotar():
    if request.method == 'POST':
        try:
            pdf_file = request.files.get('pdf')
            pages_str = request.form.get('pages', '')
            rotation = int(request.form.get('rotation', 180))
            
            if not pdf_file:
                logger.warning("No PDF file uploaded for rotation")
                return "Falta el archivo PDF", 400
            
            if not pages_str:
                logger.warning("No pages specified for rotation")
                return "No se especificaron páginas para rotar", 400
            
            if rotation not in [90, 180, 270]:
                logger.warning(f"Invalid rotation angle: {rotation}")
                return "Ángulo de rotación inválido", 400

            try:
                pages_to_rotate = set(map(int, pages_str.split(',')))
            except ValueError as e:
                logger.error(f"Invalid page format: {e}")
                return "Formato de páginas inválido", 400

            if not pdf_file.filename.lower().endswith('.pdf'):
                logger.warning(f"Invalid file extension: {pdf_file.filename}")
                return "El archivo no es un PDF válido", 400
            
            if pdf_file.mimetype != 'application/pdf':
                logger.warning(f"Invalid MIME type: {pdf_file.mimetype}")
                return "El archivo no tiene el tipo MIME correcto", 400
            
            file_content = pdf_file.read()
            if len(file_content) > 10 * 1024 * 1024:
                logger.warning(f"File too large: {len(file_content)} bytes")
                return "Archivo demasiado grande (máximo 10 MB)", 400
            
            pdf_file = io.BytesIO(file_content)
            pdf_file.seek(0)

            reader = PdfReader(pdf_file)
            total_pages = len(reader.pages)
            
            if total_pages == 0:
                logger.warning("PDF has no pages")
                return "El PDF no tiene páginas", 400
            
            # Validate page indices
            for page_idx in pages_to_rotate:
                if page_idx < 0 or page_idx >= total_pages:
                    logger.warning(f"Invalid page index: {page_idx}")
                    return f"Índice de página inválido: {page_idx}", 400
            
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
            return f"Error inesperado al rotar páginas: {str(e)}", 500

    return render_template('rotar.html')

@app.route('/extraer', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def extraer():
    if request.method == 'POST':
        try:
            pdf_file = request.files.get('pdf')
            pages_str = request.form.get('extract_pages', '')
            
            if not pdf_file:
                logger.warning("No PDF file uploaded for extraction")
                return "Falta el archivo PDF", 400
            
            if not pages_str:
                logger.warning("No pages specified for extraction")
                return "No se especificaron páginas para extraer", 400

            try:
                pages_to_extract = list(map(int, pages_str.split(',')))
            except ValueError as e:
                logger.error(f"Invalid page format: {e}")
                return "Formato de páginas inválido", 400

            if not pdf_file.filename.lower().endswith('.pdf'):
                logger.warning(f"Invalid file extension: {pdf_file.filename}")
                return "El archivo no es un PDF válido", 400
            
            if pdf_file.mimetype != 'application/pdf':
                logger.warning(f"Invalid MIME type: {pdf_file.mimetype}")
                return "El archivo no tiene el tipo MIME correcto", 400
            
            file_content = pdf_file.read()
            if len(file_content) > 10 * 1024 * 1024:
                logger.warning(f"File too large: {len(file_content)} bytes")
                return "Archivo demasiado grande (máximo 10 MB)", 400
            
            pdf_file = io.BytesIO(file_content)
            pdf_file.seek(0)

            reader = PdfReader(pdf_file)
            total_pages = len(reader.pages)
            
            if total_pages == 0:
                logger.warning("PDF has no pages")
                return "El PDF no tiene páginas", 400
            
            # Validate page indices
            for page_idx in pages_to_extract:
                if page_idx < 0 or page_idx >= total_pages:
                    logger.warning(f"Invalid page index: {page_idx}")
                    return f"Índice de página inválido: {page_idx}", 400
            
            if len(pages_to_extract) == 0:
                logger.warning("No pages to extract")
                return "Debes seleccionar al menos una página", 400
            
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
            return f"Error inesperado al extraer páginas: {str(e)}", 500

    return render_template('extraer.html')

@app.route('/info')
def info():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
