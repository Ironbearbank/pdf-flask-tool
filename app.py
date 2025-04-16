from flask import Flask, render_template, request, send_file
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import io
import os

app = Flask(__name__, template_folder='templates')

def add_image_to_pdf(pdf_file, image_file, position, replace_page=None):
    reader = PdfReader(pdf_file)
    writer = PdfWriter()

    # 画像の読み込みとサイズ調整（横幅フィット）
    image = Image.open(image_file).convert("RGB")
    page_width = float(reader.pages[0].mediabox.width)
    aspect = image.height / image.width
    new_width = int(page_width)
    new_height = int(new_width * aspect)
    resized_image = image.resize((new_width, new_height))

    image_pdf_io = io.BytesIO()
    resized_image.save(image_pdf_io, format="PDF")
    image_pdf_io.seek(0)

    image_reader = PdfReader(image_pdf_io)
    image_page = image_reader.pages[0]

    if position == 'start':
        writer.add_page(image_page)
        for page in reader.pages:
            writer.add_page(page)
    elif position == 'end':
        for page in reader.pages:
            writer.add_page(page)
        writer.add_page(image_page)
    elif position == 'replace':
        if replace_page is None or replace_page < 0 or replace_page >= len(reader.pages):
            raise ValueError("無効なページ番号です")
        for i, page in enumerate(reader.pages):
            if i == replace_page:
                writer.add_page(image_page)
            else:
                writer.add_page(page)
    else:
        raise ValueError("不正なモードが指定されました")

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/merge', methods=['POST'])
def merge():
    pdf_file = request.files['pdf']
    image_file = request.files['image']
    position = request.form['position']

    replace_page = None
    if position == 'replace':
        replace_page_input = request.form.get('replace_page', '').strip()
        if not replace_page_input:
            return "ページ番号を入力してください", 400
        try:
            replace_page = int(replace_page_input) - 1
        except ValueError:
            return "ページ番号は数値で入力してください", 400

    try:
        merged_pdf = add_image_to_pdf(pdf_file, image_file, position, replace_page)
        return send_file(merged_pdf, as_attachment=True, download_name='merged_output.pdf')
    except Exception as e:
        return f"エラーが発生しました: {str(e)}", 500

# ✅ Render用（クラウド）ではこのポート指定が無視されます
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)