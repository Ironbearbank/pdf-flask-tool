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

def convert_image_to_pdf_page(image_file, base_width=595, base_height=842):
    img = Image.open(image_file).convert("RGB")
    
    # 画像のリサイズ（アスペクト比維持）→ はみ出さないよう調整
    img_aspect = img.width / img.height
    page_aspect = base_width / base_height

    if img_aspect > page_aspect:
        # 画像が横長 → 幅を基準にリサイズ
        new_width = base_width
        new_height = int(base_width / img_aspect)
    else:
        # 画像が縦長 → 高さを基準にリサイズ
        new_height = base_height
        new_width = int(base_height * img_aspect)
    
    # 画像をリサイズ
    img = img.resize((new_width, new_height), Image.LANCZOS)

    # 背景（白）に画像を中央配置
    background = Image.new("RGB", (int(base_width), int(base_height)), (255, 255, 255))
    offset = ((base_width - new_width) // 2, (base_height - new_height) // 2)
    background.paste(img, offset)
    
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
    image_files = request.files.getlist('jpgs')

    if not pdf_file or not image_files:
        return "PDFと画像ファイルを選択してください", 400

    mode = request.form.get('mode')
    common_page = request.form.get('common_replace_page', type=int)
    replace_pages = {f'replace_page_{i}': request.form.get(f'replace_page_{i}', type=int) for i in range(len(image_files))}

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "input.pdf")
        pdf_file.save(pdf_path)

        pdf_base = os.path.splitext(sanitize(pdf_file.filename))[0]
        output_paths = []

        reader = PdfReader(pdf_path)
        first_page = reader.pages[0]
        base_width = int(first_page.mediabox.width)
        base_height = int(first_page.mediabox.height)

        for i, image_file in enumerate(image_files):
            writer = PdfWriter()
            image_page = convert_image_to_pdf_page(image_file, base_width, base_height)

            if mode == 'add_to_start':
                writer.add_page(image_page)
                for page in reader.pages:
                    writer.add_page(page)
            elif mode == 'add_to_end':
                for page in reader.pages:
                    writer.add_page(page)
                writer.add_page(image_page)
            elif mode == 'replace':
                replace_at = replace_pages.get(f'replace_page_{i}') or common_page
                replace_index = (replace_at - 1) if replace_at else -1
                
                for j, page in enumerate(reader.pages):
                    if j == replace_index:
                        writer.add_page(image_page)
                    else:
                        writer.add_page(page)
                
                # 差し替えページが範囲外なら末尾に追加
                if replace_index >= len(reader.pages):
                    writer.add_page(image_page)
            else:
                return "無効なモードが選択されました", 400

            image_base = os.path.splitext(sanitize(image_file.filename))[0]
            output_filename = f"{image_base}_{pdf_base}.pdf"
            output_path = os.path.join(tmpdir, output_filename)

            with open(output_path, 'wb') as f:
                writer.write(f)

            output_paths.append((output_path, output_filename))

        if len(output_paths) == 1:
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
