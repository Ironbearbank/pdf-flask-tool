from flask import Flask, render_template, request, send_file, make_response
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import io
import os
import zipfile
import tempfile
import re
import json
from urllib.parse import quote
from datetime import datetime

app = Flask(__name__, template_folder='templates')

def sanitize(filename: str) -> str:
    filename = os.path.basename(filename)
    return re.sub(r'[^\w.\-ぁ-んァ-ン一-龯]', '_', filename)

def convert_jpg_to_pdf_page(jpg_file, base_width=595, base_height=842):
    img = Image.open(jpg_file).convert("RGB")

    aspect = img.width / img.height
    max_width = base_width - 40
    max_height = base_height - 40

    if (max_width / aspect) <= max_height:
        new_width = int(max_width)
        new_height = int(max_width / aspect)
    else:
        new_height = int(max_height)
        new_width = int(max_height * aspect)

    img_resized = img.resize((new_width, new_height), Image.LANCZOS)

    background = Image.new("RGB", (int(base_width), int(base_height)), (255, 255, 255))
    offset = ((int(base_width) - new_width) // 2, (int(base_height) - new_height) // 2)
    background.paste(img_resized, offset)

    output_pdf = io.BytesIO()
    background.save(output_pdf, format="PDF")
    output_pdf.seek(0)
    return output_pdf

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/merge', methods=['POST'])
def merge():
    pdf_file = request.files.get('pdf')
    jpg_files = request.files.getlist('jpgs')
    jpg_order_json = request.form.get('jpg_order')

    if not pdf_file or not jpg_files or not jpg_order_json:
        return "PDFとJPGファイルを選択してください", 400

    try:
        ordered_filenames = json.loads(jpg_order_json)
    except Exception:
        return "JPGの順番情報が不正です", 400

    jpg_file_map = {f.filename: f for f in jpg_files if f and f.filename.strip()}
    jpg_files_ordered = [jpg_file_map.get(name) for name in ordered_filenames if name in jpg_file_map]

    if len(jpg_files_ordered) == 0:
        return "JPGファイルが見つかりません", 400

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "input.pdf")
        pdf_file.save(pdf_path)

        pdf_base = os.path.splitext(sanitize(pdf_file.filename))[0]
        reader = PdfReader(pdf_path)
        first_page = reader.pages[0]
        media_box = first_page.mediabox
        base_width = float(media_box.width)
        base_height = float(media_box.height)

        ordered_results = []

        for i, jpg in enumerate(jpg_files_ordered):
            writer = PdfWriter()
            jpg_pdf = convert_jpg_to_pdf_page(jpg, base_width, base_height)
            jpg_pdf_reader = PdfReader(jpg_pdf)
            jpg_page = jpg_pdf_reader.pages[0]

            mode = request.form.get('mode')
            if mode == 'add_to_start':
                writer.add_page(jpg_page)
                for page in reader.pages:
                    writer.add_page(page)
            elif mode == 'add_to_end':
                for page in reader.pages:
                    writer.add_page(page)
                writer.add_page(jpg_page)
            elif mode == 'replace':
                replace_page_key = f'replace_page_{i}'
                replace_at = request.form.get(replace_page_key, type=int)
                if not replace_at:
                    replace_at = request.form.get('common_replace_page', type=int)
                replace_index = replace_at - 1 if replace_at else -1
                for j, page in enumerate(reader.pages):
                    if j == replace_index:
                        writer.add_page(jpg_page)
                    else:
                        writer.add_page(page)
            else:
                return "無効なモードが選択されました", 400

            jpg_base = os.path.splitext(sanitize(jpg.filename))[0]
            output_filename = f"{jpg_base}_{pdf_base}.pdf"
            blob = io.BytesIO()
            writer.write(blob)
            blob.seek(0)
            ordered_results.append((output_filename, blob))

        if len(ordered_results) == 1:
            filename, blob = ordered_results[0]
            response = make_response(send_file(blob, as_attachment=True, download_name=filename))
            response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
            return response

        zip_filename = f"merged_{pdf_base}.zip"
        zip_path = os.path.join(tmpdir, zip_filename)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for filename, blob in ordered_results:
                zipinfo = zipfile.ZipInfo(filename)
                zipinfo.date_time = datetime.now().timetuple()[:6]
                zipf.writestr(zipinfo, blob.read())

        response = make_response(send_file(zip_path, as_attachment=True))
        response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(zip_filename)}"
        return response

if __name__ == '__main__':
    app.run(debug=True, port=10000)
