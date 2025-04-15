from flask import Flask, render_template, request, send_file
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import io
import os

app = Flask(__name__, template_folder='templates')

def add_image_to_pdf(pdf_file, image_file, position):
    reader = PdfReader(pdf_file)
    writer = PdfWriter()

    # PDFページのサイズを取得（最初のページ基準）
    page_width = float(reader.pages[0].mediabox.width)
    page_height = float(reader.pages[0].mediabox.height)

    # JPG画像を読み込み、RGB変換
    image = Image.open(image_file).convert("RGB")

    # 横幅フィット、アスペクト比を保持（縦が長くなる場合あり）
    aspect = image.height / image.width
    new_width = int(page_width)
    new_height = int(new_width * aspect)
    resized_image = image.resize((new_width, new_height))

    # 一時的なPDFに変換
    image_pdf_io = io.BytesIO()
    resized_image.save(image_pdf_io, format="PDF")
    image_pdf_io.seek(0)
    image_reader = PdfReader(image_pdf_io)
    image_page = image_reader.pages[0]

    # ページ追加処理
    if position == 'start':
        writer.add_page(image_page)
        for page in reader.pages:
            writer.add_page(page)
    elif position == 'end':
        for page in reader.pages:
            writer.add_page(page)
        writer.add_page(image_page)
    else:
        insert_at = int(position) - 1
        for i, page in enumerate(reader.pages):
            if i == insert_at:
                writer.add_page(image_page)
            writer.add_page(page)

    # 結果PDFを返す
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    return output

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/merge', methods=['POST'])
def merge():
    pdf_file = request.files.get('pdf')
    image_file = request.files.get('image')
    position = request.form.get('position', 'end')

    if not pdf_file or not image_file:
        return "PDFとJPGの両方を選択してください", 400

    try:
        merged_pdf = add_image_to_pdf(pdf_file, image_file, position)
        return send_file(merged_pdf, as_attachment=True, download_name='merged_output.pdf')
    except Exception as e:
        return f"処理中にエラーが発生しました: {str(e)}", 500

# ✅ Render環境では無視されるが、ローカル確認用に残す（安全設計）
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
