from flask import Blueprint, render_template, request, send_file
from PIL import Image, UnidentifiedImageError
from extensions import limiter
from utils import err, validate_pdf_upload
import pikepdf
import io
import os
import logging

logger = logging.getLogger(__name__)

convertir_bp = Blueprint('convertir', __name__)

# ── Imágenes a PDF ────────────────────────────────────────────────────────────

@convertir_bp.route('/imagenes', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def imagenes():
    if request.method == 'POST':
        try:
            files = request.files.getlist('images')

            if not files or len(files) == 0:
                return err("No se han subido imágenes")

            MAX_IMAGES = 20
            MAX_IMAGE_MB = 40
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
                    append_images=pil_images[1:],
                )
            output_stream.seek(0)

            logger.info(f"Successfully converted {len(pil_images)} images to PDF")
            return send_file(
                output_stream,
                as_attachment=True,
                download_name="images-to-pdf.pdf",
                mimetype='application/pdf',
            )

        except Exception as e:
            logger.error(f"Unexpected error in images to PDF: {e}")
            return err("Error inesperado al convertir imágenes", 500)

    return render_template('imagenes.html')


# ── Comprimir ─────────────────────────────────────────────────────────────────

COMPRESSION_LEVELS = {
    'leve':     {'quality': None, 'label': 'Leve',     'max_mb': 40},
    'media':    {'quality': 60,   'label': 'Media',    'max_mb': 30},
    'agresiva': {'quality': 35,   'label': 'Agresiva', 'max_mb': 20},
}


def _recompress_page_images(page, jpeg_quality):
    """Recompress JPEG-compatible images in a page at the given quality."""
    try:
        resources = page.get('/Resources')
        if resources is None:
            return
        xobjects = resources.get('/XObject')
        if xobjects is None:
            return
        for name in list(xobjects.keys()):
            try:
                xobj = xobjects[name]
                if str(xobj.get('/Subtype', '')) != '/Image':
                    continue
                pdfimage = pikepdf.PdfImage(xobj)
                pil_image = pdfimage.as_pil_image()
                if pil_image.mode in ('RGBA', 'P', 'LA'):
                    pil_image = pil_image.convert('RGB')
                elif pil_image.mode not in ('RGB', 'L'):
                    pil_image = pil_image.convert('RGB')
                buf = io.BytesIO()
                pil_image.save(buf, format='JPEG', quality=jpeg_quality, optimize=True)
                xobj.write(buf.getvalue(), filter=pikepdf.Name('/DCTDecode'))
                if '/DecodeParms' in xobj:
                    del xobj['/DecodeParms']
            except Exception:
                pass
    except Exception:
        pass


@convertir_bp.route('/comprimir', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def comprimir():
    if request.method == 'POST':
        try:
            pdf_file = request.files.get('pdf')
            level = request.form.get('level', 'media')

            if level not in COMPRESSION_LEVELS:
                return err("Nivel de compresión inválido")

            level_cfg = COMPRESSION_LEVELS[level]
            stream, error = validate_pdf_upload(pdf_file, max_mb=level_cfg['max_mb'])
            if error:
                return error

            original_size = len(stream.getvalue())

            try:
                stream.seek(0)
                pdf = pikepdf.open(stream)
            except Exception as e:
                logger.error(f"pikepdf open error: {e}")
                return err("No se pudo abrir el PDF. ¿Está dañado o protegido?")

            if pdf.is_encrypted:
                return err("El PDF está protegido con contraseña")
            if len(pdf.pages) == 0:
                return err("El PDF no tiene páginas")

            jpeg_quality = level_cfg['quality']
            if jpeg_quality is not None:
                for page in pdf.pages:
                    _recompress_page_images(page, jpeg_quality)

            output_stream = io.BytesIO()
            pdf.save(
                output_stream,
                compress_streams=True,
                object_stream_mode=pikepdf.ObjectStreamMode.preserve,
            )
            output_stream.seek(0)

            compressed_size = len(output_stream.getvalue())
            reduction = round((1 - compressed_size / original_size) * 100, 1)

            original_filename = pdf_file.filename or 'documento.pdf'
            output_filename = f"compress-{original_filename}"

            logger.info(
                f"Compressed PDF [{level}]: {original_size} → {compressed_size} bytes "
                f"({reduction}% reduction)"
            )

            response = send_file(
                output_stream,
                as_attachment=True,
                download_name=output_filename,
                mimetype='application/pdf',
            )
            response.headers['X-Original-Size'] = str(original_size)
            response.headers['X-Compressed-Size'] = str(compressed_size)
            response.headers['X-Reduction-Percent'] = str(reduction)
            return response

        except Exception as e:
            logger.error(f"Unexpected error in compression: {e}")
            return err("Error inesperado al comprimir el PDF", 500)

    return render_template('comprimir.html')
