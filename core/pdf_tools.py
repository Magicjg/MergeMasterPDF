from pathlib import Path
import tempfile

from PIL import Image
from pypdf import PdfReader, PdfWriter

try:
    import fitz
    FITZ_AVAILABLE = True
except Exception:
    fitz = None
    FITZ_AVAILABLE = False


def image_to_pdf(image_path, temp_files):
    image = Image.open(image_path)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    elif image.mode != "RGB":
        image = image.convert("RGB")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_pdf_path = temp_file.name
    temp_file.close()
    image.save(temp_pdf_path, "PDF", resolution=100.0)
    temp_files.append(temp_pdf_path)
    return temp_pdf_path


def append_source_to_writer(writer, file_path, temp_files):
    ext = Path(file_path).suffix.lower()
    source_pdf = file_path if ext == ".pdf" else image_to_pdf(file_path, temp_files)
    writer.append(source_pdf)


def merge_sources(files, save_path, temp_files, progress=None):
    writer = PdfWriter()
    total_files = len(files)
    for index, file_path in enumerate(files, start=1):
        append_source_to_writer(writer, file_path, temp_files)
        if progress:
            progress(index, total_files, f"Procesando {index} de {total_files}: {Path(file_path).name}")
    with open(save_path, "wb") as output_file:
        writer.write(output_file)


def split_pdf_pages(pdf_path, output_folder, output_name_factory, progress=None):
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    for index, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        output_file = Path(output_folder) / output_name_factory(index)
        with open(output_file, "wb") as f:
            writer.write(f)
        if progress:
            progress(index, total_pages, f"Separando pagina {index} de {total_pages}")
    return total_pages


def extract_pages(pdf_path, page_numbers, save_path, progress=None):
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    total = len(page_numbers)
    for index, page_number in enumerate(page_numbers, start=1):
        writer.add_page(reader.pages[page_number - 1])
        if progress:
            progress(index, total, "Extrayendo paginas...")
    with open(save_path, "wb") as f:
        writer.write(f)


def delete_pages(pdf_path, pages_to_remove, save_path, progress=None):
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    pages_to_remove_zero = {p - 1 for p in pages_to_remove}
    writer = PdfWriter()
    kept_pages = [i for i in range(total_pages) if i not in pages_to_remove_zero]
    count = 0
    for i in range(total_pages):
        if i not in pages_to_remove_zero:
            writer.add_page(reader.pages[i])
            count += 1
            if progress:
                progress(count, max(len(kept_pages), 1), "Eliminando paginas...")
    with open(save_path, "wb") as f:
        writer.write(f)


def rotate_pages(pdf_path, pages_to_rotate, degrees, save_path, progress=None):
    reader = PdfReader(pdf_path)
    total_pages = len(reader.pages)
    pages_to_rotate_zero = {p - 1 for p in pages_to_rotate}
    writer = PdfWriter()
    for i in range(total_pages):
        page = reader.pages[i]
        if i in pages_to_rotate_zero:
            if hasattr(page, "rotate"):
                page = page.rotate(degrees)
            elif hasattr(page, "rotate_clockwise"):
                page = page.rotate_clockwise(degrees)
        writer.add_page(page)
        if progress:
            progress(i + 1, total_pages, "Rotando paginas...")
    with open(save_path, "wb") as f:
        writer.write(f)


def reorder_pages(pdf_path, order, save_path, progress=None):
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    total_pages = len(order)
    for index, page_number in enumerate(order, start=1):
        writer.add_page(reader.pages[page_number - 1])
        if progress:
            progress(index, total_pages, "Reordenando paginas...")
    with open(save_path, "wb") as f:
        writer.write(f)


def compress_pdf(pdf_path, save_path):
    if not FITZ_AVAILABLE:
        raise RuntimeError("PyMuPDF no esta disponible.")
    original_size = Path(pdf_path).stat().st_size
    doc = fitz.open(pdf_path)
    doc.save(save_path, garbage=4, deflate=True, clean=True)
    doc.close()
    new_size = Path(save_path).stat().st_size
    return original_size, new_size, max(0, original_size - new_size)


def export_pdf_to_images(pdf_path, output_folder, base_name, dpi, progress=None):
    if not FITZ_AVAILABLE:
        raise RuntimeError("PyMuPDF no esta disponible.")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    zoom = dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    for index, page in enumerate(doc, start=1):
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        output_file = Path(output_folder) / f"{base_name}_pagina_{index}.png"
        pix.save(str(output_file))
        if progress:
            progress(index, total_pages, "Exportando paginas como imagenes...")
    doc.close()
    return total_pages
