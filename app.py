from flask import Flask, render_template, request, send_file
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import fitz  # PyMuPDF
import io, os, zipfile, tempfile

app = Flask(__name__, template_folder='templates')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/merge', methods=['POST'])
def merge():
    pdf_file = request.files.get('pdf_file')
    images = request.files.getlist('images')
    mode = request.form.get('mode')

    if not pdf_file or not images:
        return "PDFファイルまたは画像ファイルが指定されていません。", 400

    temp_dir = tempfile.mkdtemp()
    output_files = []
    pdf_bytes = pdf_file.read()

    for image in images:
        pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
        img = Image.open(image).convert("RGB")
        pdf_name = f"{os.path.splitext(image.filename)[0]}_{pdf_file.filename}"
        output_path = os.path.join(temp_dir, pdf_name)

        writer = PdfWriter()

        if mode == 'replace':
            replace_page = int(request.form.get('replace_page', 1)) - 1
            new_pdf_path = create_image_pdf_fitz(img, pdf_reader.pages[replace_page])
            new_page_reader = PdfReader(new_pdf_path)
            for i, page in enumerate(pdf_reader.pages):
                writer.add_page(new_page_reader.pages[0] if i == replace_page else page)

        elif mode == 'add':
            add_position = request.form.get('add_position')
            custom_page_raw = request.form.get('custom_page', '').strip()
            custom_page = int(custom_page_raw) - 1 if custom_page_raw.isdigit() else 0
            new_pdf_path = create_image_pdf_fitz(img, pdf_reader.pages[0])
            new_page_reader = PdfReader(new_pdf_path)

            if add_position == 'start':
                writer.add_page(new_page_reader.pages[0])
                for page in pdf_reader.pages:
                    writer.add_page(page)
            elif add_position == 'end':
                for page in pdf_reader.pages:
                    writer.add_page(page)
                writer.add_page(new_page_reader.pages[0])
            elif add_position == 'custom':
                for i, page in enumerate(pdf_reader.pages):
                    if i == custom_page:
                        writer.add_page(new_page_reader.pages[0])
                    writer.add_page(page)
        else:
            return "無効なモードです。", 400

        with open(output_path, 'wb') as f:
            writer.write(f)

        output_files.append(output_path)

    if len(output_files) == 1:
        return send_file(output_files[0], as_attachment=True)
    else:
        zip_path = os.path.join(temp_dir, f"merged_{pdf_file.filename}.zip")
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file in output_files:
                zipf.write(file, os.path.basename(file))
        return send_file(zip_path, as_attachment=True, download_name=f"merged_{pdf_file.filename}.zip")

def create_image_pdf_fitz(img, reference_page):
    page_width = float(reference_page.mediabox.width)
    page_height = float(reference_page.mediabox.height)

    img_width, img_height = img.size
    img_aspect = img_height / img_width
    page_aspect = page_height / page_width

    if img_aspect > page_aspect:
        target_height = page_height
        target_width = page_height / img_aspect
    else:
        target_width = page_width
        target_height = page_width * img_aspect

    x_offset = (page_width - target_width) / 2
    y_offset = (page_height - target_height) / 2

    img_byte = io.BytesIO()
    img.save(img_byte, format='PNG')
    img_byte.seek(0)

    doc = fitz.open()
    page = doc.new_page(width=page_width, height=page_height)
    img_rect = fitz.Rect(x_offset, y_offset, x_offset + target_width, y_offset + target_height)
    page.insert_image(img_rect, stream=img_byte.read(), keep_proportion=True)

    temp_pdf_path = os.path.join(tempfile.gettempdir(), f"fitz_page_{os.urandom(4).hex()}.pdf")
    doc.save(temp_pdf_path)
    doc.close()

    return temp_pdf_path

@app.route('/reverse', methods=['POST'])
def reverse():
    pdf_file = request.files.get('pdf_file')
    reverse_start = int(request.form.get('reverse_start', 0))
    reverse_end = int(request.form.get('reverse_end', 0))

    if not pdf_file:
        return "PDFファイルが選択されていません。", 400

    temp_dir = tempfile.mkdtemp()
    output_path = os.path.join(temp_dir, "reversed.pdf")

    try:
        reader = PdfReader(pdf_file)
        total_pages = len(reader.pages)

        if reverse_start + reverse_end >= total_pages:
            return "中間ページが存在しません。", 400

        writer = PdfWriter()

        for i in range(reverse_start):
            writer.add_page(reader.pages[i])

        mid_pages = reader.pages[reverse_start:total_pages - reverse_end]

        i = 0
        while i < len(mid_pages):
            if i + 1 < len(mid_pages):
                writer.add_page(mid_pages[i + 1])
                writer.add_page(mid_pages[i])
                i += 2
            else:
                writer.add_page(mid_pages[i])
                i += 1

        for i in range(total_pages - reverse_end, total_pages):
            writer.add_page(reader.pages[i])

        with open(output_path, 'wb') as f:
            writer.write(f)

        return send_file(output_path, as_attachment=True, download_name="reversed.pdf")

    except Exception as e:
        return f"エラーが発生しました: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
