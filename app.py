# ✅ app.py（ポート自動検出付き、ブラウザ自動起動、ログ出力）

from flask import Flask, render_template, request, send_file
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import threading
import webbrowser
import tempfile
import os
import sys
import io
import time
import logging
import socket

# ✅ テンプレートパス解決（PyInstaller対応）
if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.dirname(os.path.abspath(__file__))

template_path = os.path.join(base_path, 'templates')

# ✅ Flask アプリ生成
app = Flask(__name__, template_folder=template_path)

# ✅ ログ設定
log_file_path = os.path.join(tempfile.gettempdir(), "flask_app_log.txt")
file_handler = logging.FileHandler(log_file_path, mode='w', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s in %(module)s: %(message)s"))
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info("🚀 app.py started")

# ✅ 利用可能なポートを探す
def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

PORT = find_free_port()

@app.route('/')
def index():
    try:
        app.logger.info(f"📂 template_folder = {app.template_folder}")
        app.logger.info(f"📄 template files = {os.listdir(app.template_folder)}")
        return render_template('index.html')
    except Exception as e:
        app.logger.error(f"❌ テンプレートエラー: {e}")
        return f"テンプレート読み込みエラー: {str(e)}", 500

@app.route('/merge', methods=['POST'])
def merge():
    pdf_file = request.files.get('pdf')
    jpg_files = request.files.getlist('jpgs')
    mode = request.form.get('mode')

    replace_page = None
    if mode == "replace":
        try:
            replace_page = int(request.form.get('replace_page', '1')) - 1
        except ValueError:
            return "有効なページ番号を入力してください", 400

    if not pdf_file or not jpg_files:
        return "PDFとJPGの両方を選択してください", 400

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = os.path.join(temp_dir, 'original.pdf')
            pdf_file.save(pdf_path)
            pdf_reader = PdfReader(pdf_path)
            writer = PdfWriter()

            def convert_jpg_to_pdf_page(jpg_file):
                img = Image.open(jpg_file).convert("RGB")
                width_px = int(210 / 0.264583)
                height_px = int(297 / 0.264583)
                img = img.resize((width_px, height_px), Image.LANCZOS)
                temp_pdf = os.path.join(temp_dir, f"{jpg_file.filename}_temp.pdf")
                img.save(temp_pdf, "PDF", quality=100)
                return PdfReader(temp_pdf).pages[0]

            if mode == "add_to_start":
                for jpg in jpg_files:
                    writer.add_page(convert_jpg_to_pdf_page(jpg))
                for page in pdf_reader.pages:
                    writer.add_page(page)

            elif mode == "add_to_end":
                for page in pdf_reader.pages:
                    writer.add_page(page)
                for jpg in jpg_files:
                    writer.add_page(convert_jpg_to_pdf_page(jpg))

            elif mode == "replace":
                for i, page in enumerate(pdf_reader.pages):
                    if i == replace_page and jpg_files:
                        writer.add_page(convert_jpg_to_pdf_page(jpg_files[0]))
                    else:
                        writer.add_page(page)
            else:
                return "不正なモードが選択されました", 400

            output = io.BytesIO()
            writer.write(output)
            output.seek(0)

            return send_file(
                output,
                as_attachment=True,
                download_name="merged_output.pdf",
                mimetype='application/pdf'
            )

    except Exception as e:
        app.logger.error(f"❌ mergeエラー: {e}")
        return f"エラーが発生しました: {str(e)}", 500

def launch_browser():
    time.sleep(1.5)
    webbrowser.open(f"http://127.0.0.1:{PORT}")

if __name__ == '__main__':
    threading.Thread(target=launch_browser).start()
    app.logger.info("🧭 Flask 起動")
    app.run(debug=False, port=PORT)
