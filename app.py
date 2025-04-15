from flask import Flask, render_template, request, send_file
from PyPDF2 import PdfReader, PdfWriter
from PIL import Image
import io
import os

app = Flask(__name__, template_folder='templates')

def find_free_port(start=5050, end=5100):
    import socket
    for port in range(start, end):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(('localhost', port)) != 0:
                return port
    raise OSError("No free ports available")

def add_image_to_pdf(pdf_file, image_file, position):
    reader = PdfReader(pdf_file)
    writer = PdfWriter()

    # convert image
    image = Image.open(image_file).convert("RGB")
    page_width = float(reader.pages[0].mediabox.width)
    page_height = float(reader.pages[0].mediabox.height)

    # リサイズ：横幅フィット・縦は自動で（アスペクト比保持）
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
    else:
        insert_at = int(position) - 1
        for i, page in enumerate(reader.pages):
            if i == insert_at:
                writer.add_page(image_page)
            writer.add_page(page)

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
    merged_pdf = add_image_to_pdf(pdf_file, image_file, position)
    return send_file(merged_pdf, as_attachment=True, download_name='merged_output.pdf')

if __name__ == '__main__':
    port = find_free_port()
    print(f"🚀 app.py started on http://localhost:{port}")
    import webbrowser
    webbrowser.open(f"http://localhost:{port}")
    app.run(port=port)
