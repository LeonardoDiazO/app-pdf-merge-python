from flask import Flask, render_template, request, send_file, redirect, url_for, after_this_request
from PyPDF2 import PdfReader, PdfWriter
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import io

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Necesario para Flask-Limiter y flash()
limiter = Limiter(get_remote_address, app=app)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

@app.route('/')
def index():
    return render_template('index.html')  # Página informativa

@app.route('/unir', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def unir():
    if request.method == 'POST':
        files = request.files.getlist('pdfs')
        order = request.form.get('order', '')
        if not order:
            return "Orden de archivos no especificada", 400

        try:
            order_indices = list(map(int, order.split(",")))
        except ValueError:
            return "Formato de orden inválido", 400

        uploaded_files = []
        for i, file in enumerate(files):
            if not file.filename.endswith('.pdf') or file.mimetype != 'application/pdf':
                return "Archivo no válido", 400
            uploaded_files.append(io.BytesIO(file.read()))

        try:
            ordered_files = [uploaded_files[i] for i in order_indices]
        except IndexError:
            return "Error en la correspondencia del orden", 400

        writer = PdfWriter()
        for f in ordered_files:
            f.seek(0)
            reader = PdfReader(f)
            for page in reader.pages:
                writer.add_page(page)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)
        return send_file(output_stream, as_attachment=True, download_name="merged_output.pdf")

    return render_template('unir.html')

@app.route('/eliminar', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def eliminar():
    if request.method == 'POST':
        pdf_file = request.files.get('pdf')
        pages_str = request.form.get('remove_pages', '')
        if not pdf_file or not pages_str:
            return "Falta el archivo o las páginas a eliminar", 400

        try:
            pages_to_remove = list(map(int, pages_str.split(',')))
        except ValueError:
            return "Formato de páginas inválido", 400

        if not pdf_file.filename.endswith('.pdf') or pdf_file.mimetype != 'application/pdf':
            return "Archivo no válido", 400
        if len(pdf_file.read()) > 5 * 1024 * 1024:
            return "Archivo demasiado grande", 400
        pdf_file.seek(0)

        reader = PdfReader(pdf_file)
        writer = PdfWriter()

        for i, page in enumerate(reader.pages):
            if i not in pages_to_remove:
                writer.add_page(page)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)
        return send_file(output_stream, as_attachment=True, download_name="cleaned_output.pdf")

    return render_template('eliminar.html')

@app.route('/info')
def info():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
