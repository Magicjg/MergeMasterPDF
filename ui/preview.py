from PIL import Image, ImageTk

try:
    import fitz
    FITZ_AVAILABLE = True
except Exception:
    fitz = None
    FITZ_AVAILABLE = False


def render_image_preview(image_path, max_size=(800, 680)):
    image = Image.open(image_path)
    image.thumbnail(max_size)
    photo = ImageTk.PhotoImage(image)
    return photo, image.width, image.height


def render_pdf_page(pdf_path, page_index, zoom, rotation=0):
    if not FITZ_AVAILABLE:
        raise RuntimeError("PyMuPDF no esta disponible.")
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_index)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        if rotation:
            image = image.rotate(-rotation, expand=True)
        photo = ImageTk.PhotoImage(image)
        return photo, image.width, image.height
    finally:
        doc.close()


def render_pdf_thumbnail(pdf_path, page_index, rotation=0, zoom=0.35):
    return render_pdf_page(pdf_path, page_index, zoom, rotation)


def get_pdf_page_width(pdf_path, page_index):
    if not FITZ_AVAILABLE:
        raise RuntimeError("PyMuPDF no esta disponible.")
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(page_index)
        return page.rect.width
    finally:
        doc.close()


def calculate_fit_width_zoom(canvas_width, page_width, min_zoom=0.5, max_zoom=3.0):
    usable_width = max(320, canvas_width - 36)
    return max(min_zoom, min(max_zoom, usable_width / page_width))


def apply_thumbnail_colors(thumbnail_widgets, selected_pages, colors):
    for orig_idx, widgets in thumbnail_widgets.items():
        selected = orig_idx in selected_pages
        bg = colors["thumb_selected"] if selected else colors["thumb_normal"]
        widgets["frame"].config(bg=bg, highlightbackground=colors["accent"] if selected else colors["card_border"])
        widgets["img"].config(bg=bg)
        widgets["info"].config(bg=bg, fg=colors["fg_text"])
