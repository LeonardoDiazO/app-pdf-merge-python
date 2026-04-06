from flask import Flask, render_template
from extensions import limiter
from blueprints.organizar import organizar_bp
from blueprints.editar import editar_bp
from blueprints.convertir import convertir_bp
import os
import logging

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'supersecretkey-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 40 * 1024 * 1024  # 40 MB

limiter.init_app(app)

app.register_blueprint(organizar_bp)
app.register_blueprint(editar_bp)
app.register_blueprint(convertir_bp)


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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/info')
def info():
    return render_template('index.html')


if __name__ == '__main__':
    app.run(debug=True)
