#!/usr/bin/env python3

from flask import Flask, request, redirect, url_for, render_template, flash, abort, send_from_directory
from werkzeug.utils import secure_filename
import os, uuid, sqlite3
from datetime import datetime

# Database + upload folder setup is above this

from flask import Flask, request, redirect, url_for, render_template, send_from_directory, abort, flash
from werkzeug.utils import secure_filename

# --- CONFIG ---
app = Flask(__name__)
app.secret_key = "supersecret"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "files.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = None   # allow all files


# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_filename TEXT,
            stored_filename TEXT,
            token TEXT UNIQUE,
            uploaded_at TEXT
        )
    """)
    conn.commit()
    conn.close()


# --- DB FUNCTIONS ---
def insert_file(original_filename, stored_filename, token):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO files (original_filename, stored_filename, token, uploaded_at) VALUES (?, ?, ?, ?)',
        (original_filename, stored_filename, token, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()



def get_file_by_token(token):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT original_filename, stored_filename, token, uploaded_at FROM files WHERE token = ?', (token,))
    row = cur.fetchone()
    conn.close()
    return row


def list_files(limit=50):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, original_filename, token, uploaded_at FROM files ORDER BY id DESC LIMIT ?', (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


# --- HELPERS ---
def allowed_file(filename):
    if ALLOWED_EXTENSIONS is None:
        return True
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- ROUTES ---
@app.route('/')
def index():
    files = list_files()
    return render_template('index.html', files=files)


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('index'))

    file = request.files['file']

    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        orig = secure_filename(file.filename)
        stored_name = f"{uuid.uuid4().hex}_{orig}"
        path = os.path.join(app.config['UPLOAD_FOLDER'], stored_name)
        file.save(path)

        token = uuid.uuid4().hex[:8]
        while get_file_by_token(token) is not None:
            token = uuid.uuid4().hex[:8]

        insert_file(orig, stored_name, token)

        flash('File uploaded successfully')
        return redirect(url_for('download_page', token=token))
    else:
        flash('File type not allowed')
        return redirect(url_for('index'))


@app.route('/f/<token>')
def download_page(token):
    row = get_file_by_token(token)
    if not row:
        abort(404)

    original_filename, stored_filename, token_db, uploaded_at = row
    download_url = url_for('download_file', filename=stored_filename, _external=True)
    return render_template(
        'download.html',
        original_filename=original_filename,
        token=token_db,
        download_url=download_url,
        uploaded_at=uploaded_at
    )


@app.route('/d/<filename>')
def download_file(filename):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT stored_filename FROM files WHERE stored_filename = ?', (filename,))
    if not cur.fetchone():
        conn.close()
        abort(404)
    conn.close()

    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)


@app.errorhandler(413)
def too_large(e):
    return 'File is too large', 413


# --- START SERVER ---
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
