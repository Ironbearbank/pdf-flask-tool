from flask import Flask, render_template, request, send_file, make_response
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import io
import os
import zipfile
import tempfile
import re
from urllib.parse import quote

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
    return PdfReader(output_pdf).pages[0]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/merge', methods=['POST'])
def merge():
    pdf_file = request.files.get('pdf')
    all_jpg_files = request.files.getlist('jpgs')

    unique_jpg_files = {}
    for f in all_jpg_files:
        if f and f.filename.strip():
            unique_jpg_files[f.filename] = f
    jpg_files = list(unique_jpg_files.values())

    if not pdf_file or not jpg_files:
        return "PDFとJPGファイルを選択してください", 400

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "input.pdf")
        pdf_file.save(pdf_path)

        pdf_base = os.path.splitext(sanitize(pdf_file.filename))[0]
        output_paths = []

        reader = PdfReader(pdf_path)
        first_page = reader.pages[0]
        media_box = first_page.mediabox
        base_width = float(media_box.width)
        base_height = float(media_box.height)

        for i, jpg in enumerate(jpg_files):
            writer = PdfWriter()
            jpg_page = convert_jpg_to_pdf_page(jpg, base_width, base_height)

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
            output_path = os.path.join(tmpdir, output_filename)

            with open(output_path, 'wb') as f:
                writer.write(f)

            output_paths.append((output_path, output_filename))

        if len(jpg_files) == 1 and len(output_paths) == 1:
            path, filename = output_paths[0]
            response = make_response(send_file(path, as_attachment=True))
            response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
            return response

        zip_filename = f"merged_{pdf_base}.zip"
        zip_path = os.path.join(tmpdir, zip_filename)
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for path, name in output_paths:
                zipf.write(path, arcname=name)

        response = make_response(send_file(zip_path, as_attachment=True))
        response.headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(zip_filename)}"
        return response

if __name__ == '__main__':
    app.run(debug=True, port=10000)