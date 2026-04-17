APP_NAME = "MergeMasterPDF"
APP_VERSION = "1.0.1"

from pathlib import Path
import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog

from pypdf import PdfWriter, PdfReader
from tkinterdnd2 import DND_FILES, TkinterDnD

from core import config as config_core
from core import file_manager
from core import pdf_tools
from ui import preview as ui_preview
from ui import theme as ui_theme
from ui import widgets as ui_widgets

FITZ_AVAILABLE = ui_preview.FITZ_AVAILABLE

def get_config_file():
    return config_core.get_config_file(APP_NAME, __file__)


def get_resource_path(relative_path):
    return config_core.get_resource_path(relative_path, __file__)


CONFIG_FILE = get_config_file()
APP_ICON = get_resource_path("icono.ico")


class PDFMergerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MergeMasterPDF")
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        app_w = min(1500, max(1100, screen_w - 60))
        app_h = min(920, max(720, screen_h - 100))
        self.root.geometry(f"{app_w}x{app_h}")
        self.root.minsize(980, 680)

        try:
            if APP_ICON.exists():
                self.root.iconbitmap(default=str(APP_ICON))
        except Exception:
            pass

        # Core state
        self.files = []
        self.visible_indices = []
        self.history_messages = []
        self.temp_pdf_files = []
        self.file_info_cache = {}
        self.file_stats_cache = {}
        self.context_menu = None
        self.tooltip = None
        self.tooltip_label = None
        self.tooltip_index = None
        self.drag_start_index = None

        # Preview state
        self.selected_file_for_preview = None
        self.preview_image_refs = []
        self.thumbnail_image_refs = []
        self.current_preview_page_number = 1
        self.preview_zoom = 1.25

        # Visual page editor state
        self.editor_pdf_path = None
        self.editor_reader = None
        self.page_order = []              # list of original page indexes
        self.page_rotations = {}          # {orig_page_index: rotation}
        self.selected_pages = []          # list of original page indexes in selection order
        self.last_selected_page = None
        self.thumb_drag_start = None
        self.thumbnail_widgets = {}       # {orig_page_index: {'frame':..., 'num':..., 'img':...}}

        self.config_data = self.load_config()
        self.current_theme = self.config_data.get("theme", "dark")

        self.configure_styles()
        self.create_menubar()
        self.create_widgets()
        self.apply_theme()
        self.bind_mousewheel_helpers()
        self.load_last_session()
        self.update_action_states()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # -------------------------------------------------
    # Config / Theme
    # -------------------------------------------------
    def load_config(self):
        default_config = {
            "last_open_folder": str(Path.home()),
            "last_save_folder": str(Path.home()),
            "default_output_name": "PDF_UNIDO",
            "open_pdf_after_merge": True,
            "open_folder_after_merge": False,
            "restore_last_session": True,
            "last_session_files": [],
            "theme": "dark"
        }
        return config_core.load_config(CONFIG_FILE, default_config)

    def save_config(self):
        try:
            self.config_data["default_output_name"] = self.output_name_var.get().strip() or "PDF_UNIDO"
            self.config_data["open_pdf_after_merge"] = self.open_pdf_var.get()
            self.config_data["open_folder_after_merge"] = self.open_folder_var.get()
            self.config_data["restore_last_session"] = self.restore_session_var.get()
            self.config_data["last_session_files"] = self.files
            self.config_data["theme"] = self.current_theme
            config_core.save_config(CONFIG_FILE, self.config_data)
        except Exception as e:
            messagebox.showwarning("Aviso", f"No se pudo guardar la configuraciÃ³n:\n{e}")

    def configure_styles(self):
        self.style = ui_theme.configure_styles()

    def get_theme_colors(self):
        return ui_theme.get_theme_colors(self.current_theme)

    def toggle_theme(self):
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.apply_theme()
        self.save_config()
        self.refresh_preview_and_editor()

    # -------------------------------------------------
    # Menus / UI
    # -------------------------------------------------
    def create_menubar(self):
        self.menubar = tk.Menu(self.root)

        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(label="Agregar archivos", command=self.add_files)
        self.file_menu.add_command(label="Agregar carpeta", command=self.add_folder)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Salir", command=self.on_close)
        self.menubar.add_cascade(label="Archivo", menu=self.file_menu)

        self.project_menu = tk.Menu(self.menubar, tearoff=0)
        self.project_menu.add_command(label="Guardar proyecto", command=self.save_project)
        self.project_menu.add_command(label="Cargar proyecto", command=self.load_project)
        self.project_menu.add_separator()
        self.project_menu.add_command(label="Limpiar lista", command=self.clear_list)
        self.menubar.add_cascade(label="Proyecto", menu=self.project_menu)

        self.tools_menu = tk.Menu(self.menubar, tearoff=0)
        self.tools_menu.add_command(label="Unir y guardar", command=self.merge_files)
        self.tools_menu.add_command(label="Combinar por nombre", command=self.combine_by_name)
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label="Separar PDF", command=self.split_pdf)
        self.tools_menu.add_command(label="Extraer paginas PDF", command=self.extract_pdf_pages)
        self.tools_menu.add_command(label="Eliminar pÃ¡ginas PDF", command=self.delete_pdf_pages)
        self.tools_menu.add_command(label="Rotar pÃ¡ginas PDF", command=self.rotate_pdf_pages)
        self.tools_menu.add_command(label="Reordenar pÃ¡ginas PDF", command=self.reorder_pdf_pages)
        self.tools_menu.add_separator()
        self.tools_menu.add_command(label="Comprimir PDF", command=self.compress_pdf)
        self.tools_menu.add_command(label="Exportar PDF a imagenes", command=self.export_pdf_to_images)
        self.menubar.add_cascade(label="Herramientas", menu=self.tools_menu)

        self.settings_menu = tk.Menu(self.menubar, tearoff=0)
        self.settings_menu.add_command(label="Cambiar tema", command=self.toggle_theme)
        self.menubar.add_cascade(label="ConfiguraciÃ³n", menu=self.settings_menu)

        self.help_menu = tk.Menu(self.menubar, tearoff=0)
        self.help_menu.add_command(label="Resumen de funciones", command=self.show_features)
        self.help_menu.add_command(label="Atajos de teclado", command=self.show_shortcuts)
        self.help_menu.add_separator()
        self.help_menu.add_command(label="Acerca de / VersiÃ³n", command=self.show_about)
        self.menubar.add_cascade(label="?", menu=self.help_menu)

        self.root.config(menu=self.menubar)

    def create_button(self, parent, text, command, color):
        return ui_widgets.create_button(parent, text, command, color)

    def create_tool_button(self, parent, text, command):
        return ui_widgets.create_tool_button(parent, text, command)

    def create_widgets(self):
        c = self.get_theme_colors()

        self.header_frame = tk.Frame(self.root)
        self.header_frame.pack(fill="x", padx=16, pady=(14, 6))

        self.title_label = tk.Label(
            self.header_frame,
            text="MergeMasterPDF",
            font=("Segoe UI", 22, "bold"),
            anchor="w"
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label = tk.Label(
            self.header_frame,
            text="Organiza, combina, separa, reordena y previsualiza PDFs e imÃ¡genes desde una sola app.",
            font=("Segoe UI", 10),
            anchor="w"
        )
        self.subtitle_label.pack(anchor="w", pady=(4, 0))

        self.topbar = tk.Frame(self.root)
        self.topbar.pack(fill="x", padx=16, pady=(0, 8))

        self.file_menu_button = self.create_button(self.topbar, "+ Archivos", self.add_files, c["accent"])
        self.file_menu_button.pack(side="left", padx=(0, 8))

        self.folder_menu_button = self.create_button(self.topbar, "+ Carpeta", self.add_folder, c["accent"])
        self.folder_menu_button.pack(side="left", padx=(0, 8))

        self.save_project_button = self.create_tool_button(self.topbar, "Guardar proyecto", self.save_project)
        self.save_project_button.pack(side="left", padx=(6, 6))

        self.load_project_button = self.create_tool_button(self.topbar, "Cargar proyecto", self.load_project)
        self.load_project_button.pack(side="left", padx=(0, 6))

        self.theme_button = self.create_tool_button(self.topbar, "Tema", self.toggle_theme)
        self.theme_button.pack(side="right")

        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        screen_w = self.root.winfo_screenwidth()
        left_width = max(340, min(430, int(screen_w * 0.27)))
        right_width = max(260, min(320, int(screen_w * 0.20)))

        # LEFT PANEL: file loading/list
        self.left_frame = tk.Frame(self.main_frame, bd=0, highlightthickness=1)
        self.left_frame.pack(side="left", fill="both", expand=False, padx=(0, 10))
        self.left_frame.configure(width=left_width)
        self.left_frame.pack_propagate(False)

        # CENTER PANEL: preview + thumbnails
        self.center_frame = tk.Frame(self.main_frame, bd=0, highlightthickness=1)
        self.center_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))

        # RIGHT PANEL: tools only (scrollable)
        self.right_frame = tk.Frame(self.main_frame, bd=0, highlightthickness=1)
        self.right_frame.pack(side="right", fill="y")
        self.right_frame.configure(width=right_width)
        self.right_frame.pack_propagate(False)

        self.right_canvas = tk.Canvas(self.right_frame, bd=0, highlightthickness=0)
        self.right_scrollbar = tk.Scrollbar(self.right_frame, orient="vertical", command=self.right_canvas.yview)
        self.right_scrollbar.pack(side="right", fill="y")
        self.right_canvas.pack(side="left", fill="both", expand=True)
        self.right_canvas.configure(yscrollcommand=self.right_scrollbar.set)

        self.right_scrollable = tk.Frame(self.right_canvas, bd=0)
        self.right_window = self.right_canvas.create_window((0, 0), window=self.right_scrollable, anchor="nw")
        self.right_scrollable.bind("<Configure>", self.on_right_scrollable_configure)
        self.right_canvas.bind("<Configure>", self.on_right_canvas_configure)

        # ---------- LEFT CONTENT ----------
        self.drop_wrapper = tk.Frame(self.left_frame, bd=0, highlightthickness=1)
        self.drop_wrapper.pack(fill="x", padx=12, pady=(12, 10))

        self.drop_area = tk.Label(
            self.drop_wrapper,
            text="Arrastra aqui PDFs, imagenes o carpetas completas\nTambien puedes usar los botones superiores",
            font=("Segoe UI", 11, "bold"),
            relief="flat",
            bd=0,
            height=3,
            justify="center"
        )
        self.drop_area.pack(fill="x", padx=10, pady=10)
        self.drop_area.drop_target_register(DND_FILES)
        self.drop_area.dnd_bind("<<Drop>>", self.on_drop)

        self.output_frame = tk.Frame(self.left_frame)
        self.output_frame.pack(fill="x", padx=12, pady=(0, 10))

        self.output_label = tk.Label(
            self.output_frame,
            text="Nombre del PDF final",
            font=("Segoe UI", 10, "bold"),
            anchor="w"
        )
        self.output_label.pack(anchor="w", pady=(0, 6))

        self.output_name_var = tk.StringVar(value=self.config_data.get("default_output_name", "PDF_UNIDO"))
        self.output_entry = tk.Entry(
            self.output_frame,
            textvariable=self.output_name_var,
            font=("Segoe UI", 11),
            relief="flat",
            bd=10
        )
        self.output_entry.pack(fill="x")

        self.options_frame = tk.Frame(self.left_frame)
        self.options_frame.pack(fill="x", padx=12, pady=(0, 10))

        self.open_pdf_var = tk.BooleanVar(value=self.config_data.get("open_pdf_after_merge", True))
        self.open_folder_var = tk.BooleanVar(value=self.config_data.get("open_folder_after_merge", False))
        self.restore_session_var = tk.BooleanVar(value=self.config_data.get("restore_last_session", True))

        self.open_pdf_check = tk.Checkbutton(
            self.options_frame,
            text="Abrir PDF al terminar",
            variable=self.open_pdf_var,
            font=("Segoe UI", 9)
        )
        self.open_pdf_check.pack(anchor="w")

        self.open_folder_check = tk.Checkbutton(
            self.options_frame,
            text="Abrir carpeta al terminar",
            variable=self.open_folder_var,
            font=("Segoe UI", 9)
        )
        self.open_folder_check.pack(anchor="w", pady=(2, 0))

        self.restore_session_check = tk.Checkbutton(
            self.options_frame,
            text="Restaurar ultima sesion",
            variable=self.restore_session_var,
            command=self.save_config,
            font=("Segoe UI", 9)
        )
        self.restore_session_check.pack(anchor="w", pady=(2, 0))

        self.reorder_tip_label = tk.Label(
            self.options_frame,
            text="Alt + arrastrar reordena archivos",
            font=("Segoe UI", 9, "italic"),
            anchor="w"
        )
        self.reorder_tip_label.pack(anchor="w", pady=(6, 0))

        self.list_card = tk.Frame(self.left_frame, bd=0, highlightthickness=1)
        self.list_card.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        self.list_header = tk.Label(
            self.list_card,
            text="Archivos cargados",
            font=("Segoe UI", 10, "bold"),
            anchor="w"
        )
        self.list_header.pack(fill="x", padx=10, pady=(10, 8))

        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", self.on_filter_change)
        self.filter_entry = tk.Entry(
            self.list_card,
            textvariable=self.filter_var,
            font=("Segoe UI", 10),
            relief="flat",
            bd=8
        )
        self.filter_entry.pack(fill="x", padx=10, pady=(0, 8))

        self.list_container = tk.Frame(self.list_card)
        self.list_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.listbox = tk.Listbox(
            self.list_container,
            selectmode=tk.EXTENDED,
            font=("Segoe UI", 10),
            bd=0,
            highlightthickness=0,
            activestyle="none"
        )
        self.listbox.pack(side="left", fill="both", expand=True)

        self.list_scrollbar = tk.Scrollbar(self.list_container, orient="vertical", command=self.listbox.yview)
        self.list_scrollbar.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=self.list_scrollbar.set)

        self.listbox.bind("<Motion>", self.on_listbox_motion)
        self.listbox.bind("<Leave>", self.on_listbox_leave)
        self.listbox.bind("<Double-Button-1>", self.open_selected_file)
        self.listbox.bind("<Button-3>", self.show_context_menu)
        self.listbox.bind("<Alt-Button-1>", self.on_drag_start)
        self.listbox.bind("<Alt-B1-Motion>", self.on_drag_motion)
        self.listbox.bind("<<ListboxSelect>>", self.on_listbox_select)

        self.info_card = tk.Frame(self.left_frame, bd=0, highlightthickness=1)
        self.info_card.pack(fill="x", padx=12, pady=(0, 12))

        self.status_label = tk.Label(self.info_card, text="0 archivos cargados", font=("Segoe UI", 9, "bold"), anchor="w")
        self.status_label.pack(fill="x", padx=10, pady=(10, 2))

        self.summary_label = tk.Label(self.info_card, text="Total archivos: 0 | Total pÃ¡ginas estimadas: 0 | TamaÃ±o total: 0 B", font=("Segoe UI", 9), anchor="w")
        self.summary_label.pack(fill="x", padx=10, pady=(0, 8))

        self.progress_label = tk.Label(self.info_card, text="", font=("Segoe UI", 9), anchor="w")
        self.progress_label.pack(fill="x", padx=10, pady=(0, 4))

        self.progress = ttk.Progressbar(self.info_card, style="Custom.Horizontal.TProgressbar", orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", padx=10, pady=(0, 12))

        # ---------- CENTER CONTENT ----------
        self.preview_header = tk.Frame(self.center_frame)
        self.preview_header.pack(fill="x", padx=12, pady=(12, 8))

        self.preview_title_label = tk.Label(self.preview_header, text="Vista previa", font=("Segoe UI", 12, "bold"), anchor="w")
        self.preview_title_label.pack(side="left")

        self.preview_toolbar = tk.Frame(self.center_frame)
        self.preview_toolbar.pack(fill="x", padx=12, pady=(0, 8))

        self.preview_prev_btn = self.create_tool_button(self.preview_toolbar, "< Pagina", self.preview_prev_page)
        self.preview_prev_btn.pack(side="left", padx=(0, 6))
        self.preview_next_btn = self.create_tool_button(self.preview_toolbar, "Pagina >", self.preview_next_page)
        self.preview_next_btn.pack(side="left", padx=(0, 6))
        self.zoom_out_btn = self.create_tool_button(self.preview_toolbar, "- Zoom", self.zoom_out_preview)
        self.zoom_out_btn.pack(side="left", padx=(0, 6))
        self.zoom_in_btn = self.create_tool_button(self.preview_toolbar, "+ Zoom", self.zoom_in_preview)
        self.zoom_in_btn.pack(side="left", padx=(0, 6))
        self.fit_width_btn = self.create_tool_button(self.preview_toolbar, "Ajustar ancho", self.fit_width_preview)
        self.fit_width_btn.pack(side="left", padx=(0, 6))

        self.preview_info_label = tk.Label(
            self.center_frame,
            text="Selecciona un archivo para ver la vista previa.",
            anchor="w",
            justify="left",
            font=("Segoe UI", 9)
        )
        self.preview_info_label.pack(fill="x", padx=12, pady=(0, 8))

        self.preview_container = tk.Frame(self.center_frame)
        self.preview_container.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.preview_canvas = tk.Canvas(self.preview_container, bd=0, highlightthickness=1)
        self.preview_v_scrollbar = tk.Scrollbar(self.preview_container, orient="vertical", command=self.preview_canvas.yview)
        self.preview_h_scrollbar = tk.Scrollbar(self.preview_container, orient="horizontal", command=self.preview_canvas.xview)
        self.preview_canvas.configure(
            yscrollcommand=self.preview_v_scrollbar.set,
            xscrollcommand=self.preview_h_scrollbar.set
        )

        self.preview_v_scrollbar.pack(side="right", fill="y")
        self.preview_h_scrollbar.pack(side="bottom", fill="x")
        self.preview_canvas.pack(side="left", fill="both", expand=True)

        self.thumbs_title_label = tk.Label(self.center_frame, text="Miniaturas / Editor visual", font=("Segoe UI", 11, "bold"), anchor="w")
        self.thumbs_title_label.pack(fill="x", padx=12, pady=(0, 6))

        self.thumbs_info_label = tk.Label(
            self.center_frame,
            text="Las miniaturas aparecerÃ¡n cuando selecciones un PDF.",
            anchor="w",
            justify="left",
            font=("Segoe UI", 9)
        )
        self.thumbs_info_label.pack(fill="x", padx=12, pady=(0, 6))

        self.thumbs_container = tk.Frame(self.center_frame)
        self.thumbs_container.pack(fill="both", expand=False, padx=12, pady=(0, 12))

        self.thumbs_canvas = tk.Canvas(self.thumbs_container, height=250, bd=0, highlightthickness=1)
        self.thumbs_scrollbar = tk.Scrollbar(self.thumbs_container, orient="vertical", command=self.thumbs_canvas.yview)
        self.thumbs_scrollbar.pack(side="right", fill="y")
        self.thumbs_canvas.pack(side="left", fill="both", expand=True)
        self.thumbs_canvas.configure(yscrollcommand=self.thumbs_scrollbar.set)

        self.thumbs_scrollable = tk.Frame(self.thumbs_canvas, bd=0)
        self.thumbs_window = self.thumbs_canvas.create_window((0, 0), window=self.thumbs_scrollable, anchor="nw")
        self.thumbs_scrollable.bind("<Configure>", self.on_thumbs_scrollable_configure)
        self.thumbs_canvas.bind("<Configure>", self.on_thumbs_canvas_configure)

        # ---------- RIGHT CONTENT ----------
        self.quick_tools_card = tk.Frame(self.right_scrollable, bd=0, highlightthickness=1)
        self.quick_tools_card.pack(fill="x", padx=12, pady=(12, 10))
        tk.Label(self.quick_tools_card, text="Accion principal", font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 8))

        self.merge_button = self.create_button(self.quick_tools_card, "Unir y guardar", self.merge_files, c["success"])
        self.merge_button.pack(fill="x", padx=10, pady=4)
        self.combine_button = self.create_button(self.quick_tools_card, "Combinar por nombre", self.combine_by_name, c["secondary"])
        self.combine_button.pack(fill="x", padx=10, pady=(4, 10))

        self.files_tools_card = tk.Frame(self.right_scrollable, bd=0, highlightthickness=1)
        self.files_tools_card.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(self.files_tools_card, text="GestiÃ³n de archivos", font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 8))

        self.remove_button = self.create_button(self.files_tools_card, "Quitar seleccionado(s)", self.remove_selected, c["warning"])
        self.remove_button.pack(fill="x", padx=10, pady=4)
        self.clear_button = self.create_button(self.files_tools_card, "Limpiar lista", self.clear_list, c["danger"])
        self.clear_button.pack(fill="x", padx=10, pady=(4, 10))

        self.order_tools_card = tk.Frame(self.right_scrollable, bd=0, highlightthickness=1)
        self.order_tools_card.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(self.order_tools_card, text="Orden de archivos", font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 8))

        self.move_up_button = self.create_button(self.order_tools_card, "Subir", self.move_up, c["accent"])
        self.move_up_button.pack(fill="x", padx=10, pady=4)
        self.move_down_button = self.create_button(self.order_tools_card, "Bajar", self.move_down, c["accent"])
        self.move_down_button.pack(fill="x", padx=10, pady=4)
        self.sort_button = self.create_button(self.order_tools_card, "Ordenar A-Z", self.sort_files, c["accent"])
        self.sort_button.pack(fill="x", padx=10, pady=4)
        self.sort_date_button = self.create_button(self.order_tools_card, "Ordenar por fecha", self.sort_files_by_date, c["accent"])
        self.sort_date_button.pack(fill="x", padx=10, pady=4)
        self.sort_size_button = self.create_button(self.order_tools_card, "Ordenar por tamano", self.sort_files_by_size, c["accent"])
        self.sort_size_button.pack(fill="x", padx=10, pady=4)
        self.sort_type_button = self.create_button(self.order_tools_card, "Ordenar por tipo", self.sort_files_by_type, c["accent"])
        self.sort_type_button.pack(fill="x", padx=10, pady=(4, 10))

        self.pdf_tools_card = tk.Frame(self.right_scrollable, bd=0, highlightthickness=1)
        self.pdf_tools_card.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(self.pdf_tools_card, text="Herramientas PDF", font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 8))

        self.split_button = self.create_button(self.pdf_tools_card, "Separar PDF", self.split_pdf, c["warning"])
        self.split_button.pack(fill="x", padx=10, pady=4)
        self.extract_pages_button = self.create_button(self.pdf_tools_card, "Extraer paginas", self.extract_pdf_pages, c["warning"])
        self.extract_pages_button.pack(fill="x", padx=10, pady=4)
        self.delete_pages_button = self.create_button(self.pdf_tools_card, "Eliminar pÃ¡ginas PDF", self.delete_pdf_pages, c["warning"])
        self.delete_pages_button.pack(fill="x", padx=10, pady=4)
        self.rotate_pages_button = self.create_button(self.pdf_tools_card, "Rotar pÃ¡ginas PDF", self.rotate_pdf_pages, c["warning"])
        self.rotate_pages_button.pack(fill="x", padx=10, pady=4)
        self.reorder_pages_button = self.create_button(self.pdf_tools_card, "Reordenar pÃ¡ginas PDF", self.reorder_pdf_pages, c["warning"])
        self.reorder_pages_button.pack(fill="x", padx=10, pady=4)
        self.compress_button = self.create_button(self.pdf_tools_card, "Comprimir PDF", self.compress_pdf, c["secondary"])
        self.compress_button.pack(fill="x", padx=10, pady=4)
        self.export_images_button = self.create_button(self.pdf_tools_card, "PDF a imagenes", self.export_pdf_to_images, c["secondary"])
        self.export_images_button.pack(fill="x", padx=10, pady=(4, 10))

        self.editor_card = tk.Frame(self.right_scrollable, bd=0, highlightthickness=1)
        self.editor_card.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(self.editor_card, text="Editor visual", font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 8))

        self.editor_delete_btn = self.create_button(self.editor_card, "Borrar seleccionadas", self.delete_selected_thumbnail_pages, c["danger"])
        self.editor_delete_btn.pack(fill="x", padx=10, pady=4)
        self.editor_rotate_row = tk.Frame(self.editor_card)
        self.editor_rotate_row.pack(fill="x", padx=10, pady=4)

        self.editor_rotate_left_btn = self.create_button(self.editor_rotate_row, "Rotar -90", self.rotate_selected_thumbnail_pages_left, c["warning"])
        self.editor_rotate_left_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.editor_rotate_right_btn = self.create_button(self.editor_rotate_row, "Rotar +90", self.rotate_selected_thumbnail_pages_right, c["warning"])
        self.editor_rotate_right_btn.pack(side="left", fill="x", expand=True)
        self.editor_save_btn = self.create_button(self.editor_card, "Guardar PDF editado", self.save_visual_editor_pdf, c["success"])
        self.editor_save_btn.pack(fill="x", padx=10, pady=(4, 10))

        self.history_card = tk.Frame(self.right_scrollable, bd=0, highlightthickness=1)
        self.history_card.pack(fill="x", padx=12, pady=(0, 12))
        tk.Label(self.history_card, text="Historial", font=("Segoe UI", 10, "bold"), anchor="w").pack(fill="x", padx=10, pady=(10, 8))
        self.history_label = tk.Label(self.history_card, text="Sin acciones todavia.", font=("Segoe UI", 9), anchor="nw", justify="left", wraplength=250)
        self.history_label.pack(fill="x", padx=10, pady=(0, 10))

        # Status bar
        self.statusbar = tk.Frame(self.root, height=24)
        self.statusbar.pack(fill="x", side="bottom")

        self.statusbar_label = tk.Label(self.statusbar, text="Listo", anchor="w", font=("Segoe UI", 9))
        self.statusbar_label.pack(side="left", padx=10)

        self.statusbar_info = tk.Label(self.statusbar, text="0 archivos | 0 pÃ¡ginas | 0 B", anchor="e", font=("Segoe UI", 9))
        self.statusbar_info.pack(side="right", padx=10)

    def apply_theme(self):
        c = self.get_theme_colors()

        self.root.configure(bg=c["bg_main"])
        ui_theme.configure_progressbar(self.style, c)

        self.header_frame.config(bg=c["bg_main"])
        self.title_label.config(bg=c["bg_main"], fg=c["fg_title"])
        self.subtitle_label.config(bg=c["bg_main"], fg=c["muted"])

        self.topbar.config(bg=c["bg_main"])
        self.file_menu_button.config(bg=c["accent"], activebackground=c["accent"])
        self.folder_menu_button.config(bg=c["accent"], activebackground=c["accent"])
        for btn in [self.save_project_button, self.load_project_button, self.theme_button]:
            btn.config(bg=c["bg_panel"], fg=c["fg_text"], activebackground=c["accent_soft"], activeforeground=c["fg_text"])

        self.main_frame.config(bg=c["bg_main"])
        self.left_frame.config(bg=c["bg_card"], highlightbackground=c["card_border"])
        self.center_frame.config(bg=c["bg_card"], highlightbackground=c["card_border"])
        self.right_frame.config(bg=c["bg_card"], highlightbackground=c["card_border"])
        self.right_canvas.config(bg=c["bg_card"])
        self.right_scrollable.config(bg=c["bg_card"])
        self.right_scrollbar.config(bg=c["scrollbar_bg"], activebackground=c["accent"], troughcolor=c["bg_card"])

        self.drop_wrapper.config(bg=c["bg_card"], highlightbackground=c["drop_border"])
        self.drop_area.config(bg=c["accent_soft"], fg=c["accent"])

        self.output_frame.config(bg=c["bg_card"])
        self.output_label.config(bg=c["bg_card"], fg=c["fg_text"])
        self.output_entry.config(
            bg=c["entry_bg"],
            fg=c["fg_text"],
            insertbackground=c["fg_text"],
            highlightthickness=1,
            highlightbackground=c["entry_border"],
            highlightcolor=c["accent"]
        )

        self.options_frame.config(bg=c["bg_card"])
        self.open_pdf_check.config(bg=c["bg_card"], fg=c["fg_text"], activebackground=c["bg_card"], activeforeground=c["fg_text"], selectcolor=c["bg_card"])
        self.open_folder_check.config(bg=c["bg_card"], fg=c["fg_text"], activebackground=c["bg_card"], activeforeground=c["fg_text"], selectcolor=c["bg_card"])
        self.restore_session_check.config(bg=c["bg_card"], fg=c["fg_text"], activebackground=c["bg_card"], activeforeground=c["fg_text"], selectcolor=c["bg_card"])
        self.reorder_tip_label.config(bg=c["bg_card"], fg=c["muted"])

        self.list_card.config(bg=c["bg_card"], highlightbackground=c["card_border"])
        self.list_header.config(bg=c["bg_card"], fg=c["fg_text"])
        self.filter_entry.config(
            bg=c["entry_bg"],
            fg=c["fg_text"],
            insertbackground=c["fg_text"],
            highlightthickness=1,
            highlightbackground=c["entry_border"],
            highlightcolor=c["accent"]
        )
        self.list_container.config(bg=c["bg_card"])
        self.listbox.config(bg=c["bg_list"], fg=c["fg_text"], selectbackground=c["accent"], selectforeground="white")
        self.list_scrollbar.config(bg=c["scrollbar_bg"], activebackground=c["accent"], troughcolor=c["bg_card"])

        self.info_card.config(bg=c["bg_card"], highlightbackground=c["card_border"])
        self.status_label.config(bg=c["bg_card"], fg=c["fg_text"])
        self.summary_label.config(bg=c["bg_card"], fg=c["summary_fg"])
        self.progress_label.config(bg=c["bg_card"], fg=c["muted"])

        self.preview_header.config(bg=c["bg_card"])
        self.preview_toolbar.config(bg=c["bg_card"])
        self.preview_title_label.config(bg=c["bg_card"], fg=c["fg_text"])
        self.preview_info_label.config(bg=c["bg_card"], fg=c["muted"])
        self.preview_container.config(bg=c["bg_card"])
        self.preview_canvas.config(bg=c["preview_bg"], highlightbackground=c["card_border"])
        self.preview_v_scrollbar.config(bg=c["scrollbar_bg"], activebackground=c["accent"], troughcolor=c["bg_card"])
        self.preview_h_scrollbar.config(bg=c["scrollbar_bg"], activebackground=c["accent"], troughcolor=c["bg_card"])
        self.thumbs_title_label.config(bg=c["bg_card"], fg=c["fg_text"])
        self.thumbs_info_label.config(bg=c["bg_card"], fg=c["muted"])
        self.thumbs_container.config(bg=c["bg_card"])
        self.thumbs_canvas.config(bg=c["preview_bg"], highlightbackground=c["card_border"])
        self.thumbs_scrollable.config(bg=c["preview_bg"])
        self.thumbs_scrollbar.config(bg=c["scrollbar_bg"], activebackground=c["accent"], troughcolor=c["bg_card"])

        for btn in [self.preview_prev_btn, self.preview_next_btn, self.zoom_out_btn, self.zoom_in_btn, self.fit_width_btn]:
            btn.config(bg=c["bg_panel"], fg=c["fg_text"], activebackground=c["accent_soft"], activeforeground=c["fg_text"])

        for card in [self.quick_tools_card, self.files_tools_card, self.order_tools_card, self.pdf_tools_card, self.editor_card, self.history_card]:
            card.config(bg=c["bg_card"], highlightbackground=c["card_border"])
            for child in card.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(bg=c["bg_card"], fg=c["fg_text"])
        self.editor_rotate_row.config(bg=c["bg_card"])
        self.history_label.config(bg=c["bg_card"], fg=c["muted"])

        self.remove_button.config(bg=c["warning"], activebackground=c["warning"])
        self.clear_button.config(bg=c["danger"], activebackground=c["danger"])
        self.move_up_button.config(bg=c["accent"], activebackground=c["accent"])
        self.move_down_button.config(bg=c["accent"], activebackground=c["accent"])
        self.sort_button.config(bg=c["accent"], activebackground=c["accent"])
        self.sort_date_button.config(bg=c["accent"], activebackground=c["accent"])
        self.sort_size_button.config(bg=c["accent"], activebackground=c["accent"])
        self.sort_type_button.config(bg=c["accent"], activebackground=c["accent"])
        self.merge_button.config(bg=c["success"], activebackground=c["success"])
        self.combine_button.config(bg=c["secondary"], activebackground=c["secondary"])
        self.split_button.config(bg=c["warning"], activebackground=c["warning"])
        self.extract_pages_button.config(bg=c["warning"], activebackground=c["warning"])
        self.delete_pages_button.config(bg=c["warning"], activebackground=c["warning"])
        self.rotate_pages_button.config(bg=c["warning"], activebackground=c["warning"])
        self.reorder_pages_button.config(bg=c["warning"], activebackground=c["warning"])
        self.compress_button.config(bg=c["secondary"], activebackground=c["secondary"])
        self.export_images_button.config(bg=c["secondary"], activebackground=c["secondary"])
        self.editor_delete_btn.config(bg=c["danger"], activebackground=c["danger"])
        self.editor_rotate_left_btn.config(bg=c["warning"], activebackground=c["warning"])
        self.editor_rotate_right_btn.config(bg=c["warning"], activebackground=c["warning"])
        self.editor_save_btn.config(bg=c["success"], activebackground=c["success"])

        self.statusbar.config(bg=c["bg_panel"])
        self.statusbar_label.config(bg=c["bg_panel"], fg=c["muted"])
        self.statusbar_info.config(bg=c["bg_panel"], fg=c["muted"])

        self.refresh_thumbnail_colors()

    # -------------------------------------------------
    # Scrolling / helpers
    # -------------------------------------------------
    def bind_mousewheel_helpers(self):
        self.thumbs_canvas.bind_all("<Shift-MouseWheel>", self._on_mousewheel_thumbs)
        self.preview_canvas.bind_all("<Control-MouseWheel>", self._on_ctrl_mousewheel_preview)
        self.preview_canvas.bind_all("<MouseWheel>", self._on_mousewheel_preview_or_right)

    def _on_mousewheel_preview_or_right(self, event):
        try:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
            current = widget
            while current is not None:
                if current in (self.preview_canvas, self.preview_container):
                    self.preview_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    return
                if current in (self.right_canvas, self.right_scrollable):
                    self.right_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    return
                current = current.master
        except Exception:
            pass

    def _on_ctrl_mousewheel_preview(self, event):
        try:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
            current = widget
            while current is not None:
                if current in (self.preview_canvas, self.preview_container):
                    if event.delta > 0:
                        self.zoom_in_preview()
                    else:
                        self.zoom_out_preview()
                    return "break"
                current = current.master
        except Exception:
            pass

    def _on_mousewheel_thumbs(self, event):
        try:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
            current = widget
            while current is not None:
                if current in (self.thumbs_canvas, self.thumbs_scrollable):
                    self.thumbs_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                    return
                current = current.master
        except Exception:
            pass

    def on_right_scrollable_configure(self, event=None):
        self.right_canvas.configure(scrollregion=self.right_canvas.bbox("all"))

    def on_right_canvas_configure(self, event):
        self.right_canvas.itemconfig(self.right_window, width=event.width)

    def on_thumbs_scrollable_configure(self, event=None):
        self.thumbs_canvas.configure(scrollregion=self.thumbs_canvas.bbox("all"))

    def on_thumbs_canvas_configure(self, event):
        self.thumbs_canvas.itemconfig(self.thumbs_window, width=event.width)

    def normalize_path(self, path_str):
        return file_manager.normalize_path(path_str)

    def sanitize_filename(self, name):
        return file_manager.sanitize_filename(name)

    def is_supported_file(self, file_path):
        return file_manager.is_supported_file(file_path)

    def format_file_size(self, size_bytes):
        return file_manager.format_file_size(size_bytes)

    def set_statusbar_message(self, text):
        self.statusbar_label.config(text=text)
        self.add_history(text)

    def add_history(self, text):
        if not text:
            return
        self.history_messages.insert(0, text)
        self.history_messages = self.history_messages[:6]
        if hasattr(self, "history_label"):
            self.history_label.config(text="\n".join(self.history_messages) or "Sin acciones todavia.")

    def update_progress(self, value, maximum, text=None):
        self.progress["maximum"] = max(maximum, 1)
        self.progress["value"] = value
        if text is not None:
            self.progress_label.config(text=text)
        self.root.update_idletasks()

    def clear_file_info_cache(self):
        self.file_info_cache.clear()
        self.file_stats_cache.clear()

    def get_file_stats(self, file_path):
        normalized = str(Path(file_path).resolve())
        if normalized in self.file_stats_cache:
            return self.file_stats_cache[normalized]

        path_obj = Path(normalized)
        ext = path_obj.suffix.lower()
        stats = {
            "name": path_obj.name,
            "ext": ext,
            "size_bytes": 0,
            "size_text": "0 B",
            "pages": 0,
            "kind": "Archivo",
            "ok": True,
        }
        try:
            stats["size_bytes"] = path_obj.stat().st_size
            stats["size_text"] = self.format_file_size(stats["size_bytes"])
            if ext == ".pdf":
                stats["pages"] = len(PdfReader(normalized).pages)
                stats["kind"] = "PDF"
            elif ext in {".jpg", ".jpeg", ".png"}:
                stats["pages"] = 1
                stats["kind"] = "Imagen"
        except Exception:
            stats["ok"] = False
            stats["size_text"] = "?"

        self.file_stats_cache[normalized] = stats
        return stats

    def get_file_display_info(self, file_path):
        normalized = str(Path(file_path).resolve())
        if normalized in self.file_info_cache:
            return self.file_info_cache[normalized]

        stats = self.get_file_stats(normalized)
        if not stats["ok"]:
            info = f"{stats['name']} (?)"
        elif stats["ext"] == ".pdf":
            info = f"{stats['name']} ({stats['pages']} pags. | {stats['size_text']})"
        elif stats["kind"] == "Imagen":
            info = f"{stats['name']} (Imagen | {stats['size_text']})"
        else:
            info = f"{stats['name']} ({stats['size_text']})"

        self.file_info_cache[normalized] = info
        return info

    # -------------------------------------------------
    # Tooltips
    # -------------------------------------------------
    def show_tooltip(self, text, x, y):
        self.hide_tooltip()
        c = self.get_theme_colors()
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{x + 15}+{y + 10}")
        self.tooltip_label = tk.Label(
            self.tooltip,
            text=text,
            justify="left",
            bg=c["tooltip_bg"],
            fg=c["tooltip_fg"],
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=4,
            font=("Segoe UI", 9)
        )
        self.tooltip_label.pack()

    def hide_tooltip(self):
        if self.tooltip is not None:
            self.tooltip.destroy()
            self.tooltip = None
            self.tooltip_label = None
            self.tooltip_index = None

    def on_listbox_motion(self, event):
        list_index = self.listbox.nearest(event.y)
        if list_index < 0 or list_index >= len(self.visible_indices):
            self.hide_tooltip()
            return
        bbox = self.listbox.bbox(list_index)
        if bbox is None:
            self.hide_tooltip()
            return
        x, y, width, height = bbox
        if not (y <= event.y <= y + height):
            self.hide_tooltip()
            return
        file_index = self.visible_indices[list_index]
        if self.tooltip_index == file_index:
            return
        self.tooltip_index = file_index
        self.show_tooltip(self.files[file_index], event.x_root, event.y_root)

    def on_listbox_leave(self, event):
        self.hide_tooltip()

    # -------------------------------------------------
    # File ops helpers
    # -------------------------------------------------
    def open_file(self, file_path):
        try:
            os.startfile(file_path)
        except Exception as e:
            messagebox.showwarning("Aviso", f"No se pudo abrir el archivo:\n{e}")

    def open_folder(self, folder_path):
        try:
            os.startfile(folder_path)
        except Exception as e:
            messagebox.showwarning("Aviso", f"No se pudo abrir la carpeta:\n{e}")

    def open_selected_file(self, event=None):
        selected_indices = self.get_selected_indices()
        if not selected_indices:
            return
        self.open_file(self.files[selected_indices[0]])

    def show_in_folder(self, file_path):
        try:
            os.startfile(str(Path(file_path).parent))
        except Exception as e:
            messagebox.showwarning("Aviso", f"No se pudo abrir la carpeta:\n{e}")

    def copy_path_to_clipboard(self, file_path):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(file_path)
            self.root.update()
            self.set_statusbar_message("Ruta copiada al portapapeles")
        except Exception as e:
            messagebox.showwarning("Aviso", f"No se pudo copiar la ruta:\n{e}")

    # -------------------------------------------------
    # Context menu
    # -------------------------------------------------
    def get_selected_indices(self):
        indices = []
        for list_index in self.listbox.curselection():
            if 0 <= list_index < len(self.visible_indices):
                indices.append(self.visible_indices[list_index])
        return indices

    def open_current_selection(self):
        indices = self.get_selected_indices()
        if indices:
            self.open_file(self.files[indices[0]])

    def show_current_selection_in_folder(self):
        indices = self.get_selected_indices()
        if indices:
            self.show_in_folder(self.files[indices[0]])

    def copy_current_selection_path(self):
        indices = self.get_selected_indices()
        if indices:
            self.copy_path_to_clipboard(self.files[indices[0]])

    def remove_selected_no_warning(self):
        indices = self.get_selected_indices()
        if not indices:
            return
        for index in sorted(indices, reverse=True):
            removed_file = self.files[index]
            del self.files[index]
            normalized = str(Path(removed_file).resolve())
            self.file_info_cache.pop(normalized, None)
            self.file_stats_cache.pop(normalized, None)
        self.hide_tooltip()
        self.refresh_listbox()
        self.clear_preview()

    def move_selected_up_from_menu(self):
        self.move_up()

    def move_selected_down_from_menu(self):
        self.move_down()

    def show_context_menu(self, event):
        list_index = self.listbox.nearest(event.y)
        if list_index < 0 or list_index >= len(self.visible_indices):
            return
        bbox = self.listbox.bbox(list_index)
        if bbox is None:
            return
        x, y, width, height = bbox
        if not (y <= event.y <= y + height):
            return
        if list_index not in self.listbox.curselection():
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(list_index)

        selected_count = len(self.get_selected_indices())
        if self.context_menu is not None:
            self.context_menu.destroy()

        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Abrir", command=self.open_current_selection)
        self.context_menu.add_command(label="Mostrar en carpeta", command=self.show_current_selection_in_folder)
        self.context_menu.add_command(label="Copiar ruta", command=self.copy_current_selection_path)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Subir", command=self.move_selected_up_from_menu)
        self.context_menu.add_command(label="Bajar", command=self.move_selected_down_from_menu)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Quitar", command=self.remove_selected_no_warning)
        if selected_count > 1:
            self.context_menu.add_command(label=f"Quitar seleccionados ({selected_count})", command=self.remove_selected_no_warning)
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    # -------------------------------------------------
    # File collection
    # -------------------------------------------------
    def get_supported_files_from_folder(self, folder_path):
        return file_manager.get_supported_files_from_folder(folder_path)

    def add_folder_to_list(self, folder_path):
        added_files = []
        for file_path in self.get_supported_files_from_folder(folder_path):
            if file_path not in self.files:
                self.files.append(file_path)
                added_files.append(file_path)
        return added_files

    def add_file_to_list(self, file_path):
        try:
            normalized = self.normalize_path(file_path)
            if not self.is_supported_file(normalized):
                return
            if normalized not in self.files:
                self.files.append(normalized)
        except Exception:
            pass

    def build_group_key(self, file_path):
        return file_manager.build_group_key(file_path)

    def natural_sort_key(self, file_path):
        return file_manager.natural_sort_key(file_path)

    # -------------------------------------------------
    # Summary/list refresh
    # -------------------------------------------------
    def get_filter_text(self):
        if not hasattr(self, "filter_var"):
            return ""
        return self.filter_var.get().strip().lower()

    def is_filter_active(self):
        return bool(self.get_filter_text())

    def on_filter_change(self, *args):
        self.refresh_listbox()

    def get_visible_file_indices(self):
        filter_text = self.get_filter_text()
        if not filter_text:
            return list(range(len(self.files)))
        return [
            index
            for index, file_path in enumerate(self.files)
            if filter_text in Path(file_path).name.lower()
            or filter_text in str(Path(file_path).parent).lower()
        ]

    def update_status(self):
        if self.is_filter_active():
            self.status_label.config(text=f"{len(self.visible_indices)} de {len(self.files)} archivo(s) visibles")
        else:
            self.status_label.config(text=f"{len(self.files)} archivo(s) cargado(s)")

    def update_summary(self):
        total_files = len(self.files)
        total_output_pages = 0
        total_size_bytes = 0
        for file_path in self.files:
            stats = self.get_file_stats(file_path)
            total_size_bytes += stats["size_bytes"]
            total_output_pages += stats["pages"]
        total_size_text = self.format_file_size(total_size_bytes)
        self.summary_label.config(text=f"Total archivos: {total_files} | Total pÃ¡ginas estimadas: {total_output_pages} | TamaÃ±o total: {total_size_text}")
        self.statusbar_info.config(text=f"{total_files} archivos | {total_output_pages} pÃ¡ginas | {total_size_text}")

    def refresh_listbox(self):
        self.hide_tooltip()
        self.listbox.delete(0, tk.END)
        self.visible_indices = self.get_visible_file_indices()
        for file_index in self.visible_indices:
            self.listbox.insert(tk.END, self.get_file_display_info(self.files[file_index]))
        self.update_status()
        self.update_summary()
        self.update_action_states()

    def set_buttons_state(self, buttons, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        for button in buttons:
            if button is not None:
                button.config(state=state)

    def update_action_states(self):
        if not hasattr(self, "merge_button"):
            return
        has_files = bool(self.files)
        has_selection = bool(self.get_selected_indices())
        has_pdf_editor = bool(self.editor_pdf_path and self.page_order)
        filtered = self.is_filter_active()

        self.set_buttons_state([self.merge_button, self.combine_button, self.clear_button, self.sort_button, self.sort_date_button, self.sort_size_button, self.sort_type_button, self.save_project_button], has_files)
        self.set_buttons_state([self.remove_button, self.move_up_button, self.move_down_button], has_selection and not filtered)
        self.set_buttons_state([self.editor_delete_btn, self.editor_rotate_left_btn, self.editor_rotate_right_btn, self.editor_save_btn], has_pdf_editor)
        self.set_buttons_state([self.preview_prev_btn, self.preview_next_btn, self.zoom_out_btn, self.zoom_in_btn, self.fit_width_btn], has_pdf_editor)

    # -------------------------------------------------
    # Add files / drop
    # -------------------------------------------------
    def add_files(self):
        initial_dir = self.config_data.get("last_open_folder", str(Path.home()))
        files = filedialog.askopenfilenames(
            title="Selecciona PDFs o imÃ¡genes",
            filetypes=[
                ("Archivos compatibles", "*.pdf *.jpg *.jpeg *.png"),
                ("PDF", "*.pdf"),
                ("ImÃ¡genes", "*.jpg *.jpeg *.png")
            ],
            initialdir=initial_dir
        )
        if not files:
            return
        for file in files:
            self.add_file_to_list(file)
        first_folder = str(Path(files[0]).parent)
        self.config_data["last_open_folder"] = first_folder
        self.config_data["last_save_folder"] = first_folder
        self.save_config()
        self.refresh_listbox()
        self.set_statusbar_message("Archivos agregados")

    def add_folder(self):
        initial_dir = self.config_data.get("last_open_folder", str(Path.home()))
        folder = filedialog.askdirectory(title="Selecciona una carpeta", initialdir=initial_dir)
        if not folder:
            return
        added_files = self.add_folder_to_list(folder)
        if not added_files:
            messagebox.showinfo("Aviso", "No se encontraron archivos compatibles en la carpeta.")
            return
        self.config_data["last_open_folder"] = str(Path(folder))
        self.config_data["last_save_folder"] = str(Path(folder))
        self.save_config()
        self.refresh_listbox()
        self.set_statusbar_message("Carpeta agregada")

    def on_drop(self, event):
        try:
            dropped_items = self.root.tk.splitlist(event.data)
            valid_paths = []
            for item in dropped_items:
                path_obj = Path(item)
                if path_obj.is_dir():
                    valid_paths.extend(self.add_folder_to_list(path_obj))
                elif path_obj.is_file():
                    self.add_file_to_list(item)
                    if self.is_supported_file(item):
                        valid_paths.append(str(path_obj.resolve()))
            if valid_paths:
                first_folder = str(Path(valid_paths[0]).parent)
                self.config_data["last_open_folder"] = first_folder
                self.config_data["last_save_folder"] = first_folder
                self.save_config()
            self.refresh_listbox()
            self.set_statusbar_message("Elementos cargados por arrastre")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron cargar los archivos o carpetas:\n{e}")

    # -------------------------------------------------
    # List ordering
    # -------------------------------------------------
    def remove_selected(self):
        indices = self.get_selected_indices()
        if not indices:
            messagebox.showwarning("AtenciÃ³n", "Selecciona al menos un archivo para quitar.")
            return
        for index in sorted(indices, reverse=True):
            removed_file = self.files[index]
            del self.files[index]
            normalized = str(Path(removed_file).resolve())
            self.file_info_cache.pop(normalized, None)
            self.file_stats_cache.pop(normalized, None)
        self.hide_tooltip()
        self.refresh_listbox()
        self.clear_preview()
        self.set_statusbar_message("Archivo(s) quitado(s)")

    def move_up(self):
        indices = self.get_selected_indices()
        if not indices:
            messagebox.showwarning("AtenciÃ³n", "Selecciona al menos un archivo para mover.")
            return
        if indices[0] == 0:
            return
        for index in indices:
            self.files[index - 1], self.files[index] = self.files[index], self.files[index - 1]
        self.refresh_listbox()
        self.listbox.selection_clear(0, tk.END)
        for index in [i - 1 for i in indices]:
            self.listbox.selection_set(index)
        self.set_statusbar_message("Archivo(s) movido(s)")

    def move_down(self):
        indices = self.get_selected_indices()
        if not indices:
            messagebox.showwarning("AtenciÃ³n", "Selecciona al menos un archivo para mover.")
            return
        if indices[-1] == len(self.files) - 1:
            return
        for index in reversed(indices):
            self.files[index + 1], self.files[index] = self.files[index], self.files[index + 1]
        self.refresh_listbox()
        self.listbox.selection_clear(0, tk.END)
        for index in [i + 1 for i in indices]:
            self.listbox.selection_set(index)
        self.set_statusbar_message("Archivo(s) movido(s)")

    def sort_files(self):
        if not self.files:
            return
        self.files.sort(key=self.natural_sort_key)
        self.refresh_listbox()
        self.set_statusbar_message("Lista ordenada A-Z natural")

    def sort_files_by_date(self):
        if not self.files:
            return
        self.files.sort(key=lambda x: Path(x).stat().st_mtime if Path(x).exists() else 0, reverse=True)
        self.refresh_listbox()
        self.set_statusbar_message("Lista ordenada por fecha")

    def sort_files_by_size(self):
        if not self.files:
            return
        self.files.sort(key=lambda x: self.get_file_stats(x)["size_bytes"], reverse=True)
        self.refresh_listbox()
        self.set_statusbar_message("Lista ordenada por tamano")

    def sort_files_by_type(self):
        if not self.files:
            return
        self.files.sort(key=lambda x: (Path(x).suffix.lower(), self.natural_sort_key(x)))
        self.refresh_listbox()
        self.set_statusbar_message("Lista ordenada por tipo")

    def on_drag_start(self, event):
        if self.is_filter_active():
            self.drag_start_index = None
            self.set_statusbar_message("Limpia el filtro para reordenar archivos")
            return
        self.drag_start_index = self.listbox.nearest(event.y)

    def on_drag_motion(self, event):
        if self.drag_start_index is None or self.is_filter_active():
            return
        new_index = self.listbox.nearest(event.y)
        if (
            new_index == self.drag_start_index
            or new_index < 0
            or new_index >= len(self.files)
            or self.drag_start_index < 0
            or self.drag_start_index >= len(self.files)
        ):
            return
        item = self.files.pop(self.drag_start_index)
        self.files.insert(new_index, item)
        self.drag_start_index = new_index
        self.refresh_listbox()
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(new_index)
        self.set_statusbar_message("Reordenando archivos...")

    def on_listbox_select(self, event=None):
        indices = self.get_selected_indices()
        if not indices:
            self.clear_preview()
            self.update_action_states()
            return
        file_path = self.files[indices[0]]
        self.selected_file_for_preview = file_path
        self.current_preview_page_number = 1
        self.show_preview_for_file(file_path)
        self.update_action_states()

    # -------------------------------------------------
    # Preview helpers
    # -------------------------------------------------
    def clear_preview(self):
        self.selected_file_for_preview = None
        self.editor_pdf_path = None
        self.editor_reader = None
        self.page_order = []
        self.page_rotations = {}
        self.selected_pages = []
        self.last_selected_page = None
        self.preview_canvas.delete("all")
        self.preview_image_refs = []
        self.clear_thumbnails()
        self.preview_info_label.config(text="Selecciona un archivo para ver la vista previa.")
        self.thumbs_info_label.config(text="Las miniaturas aparecerÃ¡n cuando selecciones un PDF.")
        self.update_action_states()

    def refresh_preview_and_editor(self):
        if self.selected_file_for_preview and Path(self.selected_file_for_preview).exists():
            self.show_preview_for_file(self.selected_file_for_preview)
        else:
            self.clear_preview()

    def clear_thumbnails(self):
        for widget in self.thumbs_scrollable.winfo_children():
            widget.destroy()
        self.thumbnail_image_refs = []
        self.thumbnail_widgets = {}

    def show_preview_for_file(self, file_path):
        ext = Path(file_path).suffix.lower()
        self.preview_canvas.delete("all")
        self.preview_image_refs = []
        self.clear_thumbnails()

        if ext == ".pdf":
            self.load_pdf_into_visual_editor(file_path)
            self.show_current_preview_page()
            self.render_editor_thumbnails()
        elif ext in {".jpg", ".jpeg", ".png"}:
            self.editor_pdf_path = None
            self.editor_reader = None
            self.page_order = []
            self.page_rotations = {}
            self.selected_pages = []
            self.last_selected_page = None
            self.show_image_preview(file_path)
            self.thumbs_info_label.config(text="Las miniaturas interactivas estÃ¡n disponibles solo para PDFs.")
        else:
            self.preview_info_label.config(text="Vista previa no disponible para este tipo de archivo.")
            self.thumbs_info_label.config(text="Las miniaturas interactivas estÃ¡n disponibles solo para PDFs.")

    def load_pdf_into_visual_editor(self, pdf_path):
        self.editor_pdf_path = pdf_path
        self.editor_reader = PdfReader(pdf_path)
        total_pages = len(self.editor_reader.pages)
        self.page_order = list(range(total_pages))
        self.page_rotations = {i: 0 for i in range(total_pages)}
        self.selected_pages = []
        self.last_selected_page = None
        self.current_preview_page_number = 1

    def show_image_preview(self, image_path):
        try:
            photo, width, height = ui_preview.render_image_preview(image_path)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(10, 10, image=photo, anchor="nw")
            self.preview_canvas.configure(scrollregion=(0, 0, width + 20, height + 20))
            self.preview_image_refs = [photo]
            size_text = self.format_file_size(Path(image_path).stat().st_size)
            self.preview_info_label.config(text=f"Archivo: {Path(image_path).name}\nTipo: Imagen\nTamaÃ±o: {size_text}")
        except Exception as e:
            self.preview_info_label.config(text=f"No se pudo generar la vista previa de la imagen.\n{e}")

    def show_current_preview_page(self):
        if not FITZ_AVAILABLE:
            self.preview_info_label.config(text="Preview no disponible.\nInstala PyMuPDF con:\npip install pymupdf")
            return
        if not self.editor_pdf_path or not self.page_order:
            self.preview_info_label.config(text="Selecciona un PDF para ver la vista previa.")
            return

        total_pages = len(self.page_order)
        self.current_preview_page_number = max(1, min(self.current_preview_page_number, total_pages))
        display_idx = self.current_preview_page_number - 1
        orig_idx = self.page_order[display_idx]
        rotation = self.page_rotations.get(orig_idx, 0)

        try:
            photo, width, height = ui_preview.render_pdf_page(self.editor_pdf_path, orig_idx, self.preview_zoom, rotation)

            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(10, 10, image=photo, anchor="nw")
            self.preview_canvas.configure(scrollregion=(0, 0, width + 20, height + 20))
            self.preview_canvas.xview_moveto(0)
            self.preview_canvas.yview_moveto(0)
            self.preview_image_refs = [photo]

            size_text = self.format_file_size(Path(self.editor_pdf_path).stat().st_size)
            selected_count = len(self.selected_pages)
            self.preview_info_label.config(
                text=(
                    f"Archivo: {Path(self.editor_pdf_path).name}\n"
                    f"PÃ¡gina vista: {self.current_preview_page_number}/{total_pages} | PÃ¡gina original: {orig_idx + 1}\n"
                    f"RotaciÃ³n aplicada: {rotation}Â° | Zoom: {self.preview_zoom:.2f}x\n"
                    f"PÃ¡ginas seleccionadas: {selected_count} | TamaÃ±o: {size_text}"
                )
            )
        except Exception as e:
            self.preview_info_label.config(text=f"No se pudo generar la vista previa del PDF.\n{e}")

    def preview_prev_page(self):
        if not self.page_order:
            return
        if self.current_preview_page_number > 1:
            self.current_preview_page_number -= 1
            self.show_current_preview_page()

    def preview_next_page(self):
        if not self.page_order:
            return
        if self.current_preview_page_number < len(self.page_order):
            self.current_preview_page_number += 1
            self.show_current_preview_page()

    def zoom_in_preview(self):
        self.preview_zoom = min(3.0, self.preview_zoom + 0.15)
        self.show_current_preview_page()

    def zoom_out_preview(self):
        self.preview_zoom = max(0.5, self.preview_zoom - 0.15)
        self.show_current_preview_page()

    def fit_width_preview(self):
        if not FITZ_AVAILABLE or not self.editor_pdf_path or not self.page_order:
            return
        try:
            display_idx = max(0, self.current_preview_page_number - 1)
            orig_idx = self.page_order[display_idx]
            page_width = ui_preview.get_pdf_page_width(self.editor_pdf_path, orig_idx)
            self.preview_zoom = ui_preview.calculate_fit_width_zoom(self.preview_canvas.winfo_width(), page_width)
            self.show_current_preview_page()
            self.set_statusbar_message("Vista ajustada al ancho")
        except Exception:
            pass

    # -------------------------------------------------
    # Visual thumbnail editor
    # -------------------------------------------------
    def render_editor_thumbnails(self):
        self.clear_thumbnails()
        if not self.editor_pdf_path or not self.page_order:
            self.thumbs_info_label.config(text="Las miniaturas aparecerÃ¡n cuando selecciones un PDF.")
            return
        if not FITZ_AVAILABLE:
            self.thumbs_info_label.config(text="Miniaturas no disponibles.\nInstala PyMuPDF con:\npip install pymupdf")
            return

        try:
            self.thumbs_info_label.config(
                text="Click = seleccionar | Ctrl+Click = multi-selecciÃ³n | Shift+Click = rango | Arrastra una miniatura para reordenar"
            )

            for display_pos, orig_idx in enumerate(self.page_order):
                rotation = self.page_rotations.get(orig_idx, 0)
                photo, _width, _height = ui_preview.render_pdf_thumbnail(self.editor_pdf_path, orig_idx, rotation)
                self.thumbnail_image_refs.append(photo)

                item_frame = tk.Frame(self.thumbs_scrollable, bd=0, highlightthickness=2, cursor="hand2")
                item_frame.pack(fill="x", padx=6, pady=4)

                img_label = tk.Label(item_frame, image=photo, bd=0, cursor="hand2")
                img_label.pack(side="left", padx=8, pady=8)

                info_text = (
                    f"PosiciÃ³n: {display_pos + 1}\n"
                    f"PÃ¡gina original: {orig_idx + 1}\n"
                    f"RotaciÃ³n: {rotation}Â°"
                )
                info_label = tk.Label(item_frame, text=info_text, anchor="w", justify="left", font=("Segoe UI", 9, "bold"), cursor="hand2")
                info_label.pack(side="left", fill="x", expand=True, padx=(0, 8))

                self.thumbnail_widgets[orig_idx] = {
                    "frame": item_frame,
                    "img": img_label,
                    "info": info_label,
                }

                for widget in (item_frame, img_label, info_label):
                    widget.bind("<Button-1>", lambda e, p=orig_idx: self.on_thumbnail_click(e, p))
                    widget.bind("<B1-Motion>", lambda e, p=orig_idx: self.on_thumbnail_drag_motion(e, p))

            self.refresh_thumbnail_colors()
        except Exception as e:
            self.thumbs_info_label.config(text=f"No se pudieron generar las miniaturas.\n{e}")

    def refresh_thumbnail_colors(self):
        if not hasattr(self, "thumbnail_widgets"):
            return
        ui_preview.apply_thumbnail_colors(self.thumbnail_widgets, self.selected_pages, self.get_theme_colors())

    def on_thumbnail_click(self, event, orig_idx):
        state = event.state
        ctrl_pressed = bool(state & 0x0004)
        shift_pressed = bool(state & 0x0001)

        if shift_pressed and self.last_selected_page is not None and self.last_selected_page in self.page_order:
            start = self.page_order.index(self.last_selected_page)
            end = self.page_order.index(orig_idx)
            if start > end:
                start, end = end, start
            self.selected_pages = self.page_order[start:end + 1]
        elif ctrl_pressed:
            if orig_idx in self.selected_pages:
                self.selected_pages.remove(orig_idx)
            else:
                self.selected_pages.append(orig_idx)
            self.last_selected_page = orig_idx
        else:
            self.selected_pages = [orig_idx]
            self.last_selected_page = orig_idx

        if orig_idx in self.page_order:
            self.current_preview_page_number = self.page_order.index(orig_idx) + 1
        self.refresh_thumbnail_colors()
        self.show_current_preview_page()
        self.thumb_drag_start = orig_idx

    def on_thumbnail_drag_motion(self, event, orig_idx):
        if self.thumb_drag_start is None:
            return
        target_widget = event.widget.winfo_containing(event.x_root, event.y_root)
        if target_widget is None:
            return
        target_orig = self.find_thumbnail_orig_from_widget(target_widget)
        if target_orig is None or target_orig == self.thumb_drag_start:
            return
        self.reorder_thumbnail_page(self.thumb_drag_start, target_orig)
        self.thumb_drag_start = target_orig

    def find_thumbnail_orig_from_widget(self, widget):
        current = widget
        while current is not None:
            for orig_idx, widgets in self.thumbnail_widgets.items():
                if current == widgets["frame"] or current == widgets["img"] or current == widgets["info"]:
                    return orig_idx
            current = current.master
        return None

    def reorder_thumbnail_page(self, moving_orig, target_orig):
        if moving_orig not in self.page_order or target_orig not in self.page_order:
            return
        from_idx = self.page_order.index(moving_orig)
        to_idx = self.page_order.index(target_orig)
        item = self.page_order.pop(from_idx)
        self.page_order.insert(to_idx, item)
        if moving_orig in self.page_order:
            self.current_preview_page_number = self.page_order.index(moving_orig) + 1
        self.render_editor_thumbnails()
        self.show_current_preview_page()
        self.set_statusbar_message("PÃ¡ginas reordenadas visualmente")

    def delete_selected_thumbnail_pages(self):
        if not self.editor_pdf_path or not self.page_order:
            messagebox.showwarning("AtenciÃ³n", "Selecciona un PDF para editar visualmente.")
            return
        if not self.selected_pages:
            messagebox.showwarning("AtenciÃ³n", "Selecciona al menos una miniatura.")
            return
        if len(self.selected_pages) >= len(self.page_order):
            messagebox.showwarning("AtenciÃ³n", "No puedes borrar todas las pÃ¡ginas del PDF.")
            return

        confirm = messagebox.askyesno("Confirmar", f"Â¿Quieres borrar {len(self.selected_pages)} pÃ¡gina(s) seleccionada(s)?")
        if not confirm:
            return

        selected_set = set(self.selected_pages)
        self.page_order = [p for p in self.page_order if p not in selected_set]
        for p in selected_set:
            self.page_rotations.pop(p, None)

        self.selected_pages = []
        self.last_selected_page = None
        self.current_preview_page_number = min(self.current_preview_page_number, len(self.page_order))
        self.current_preview_page_number = max(1, self.current_preview_page_number)
        self.render_editor_thumbnails()
        self.show_current_preview_page()
        self.set_statusbar_message("PÃ¡ginas borradas del editor visual")

    def rotate_selected_thumbnail_pages(self, delta):
        if not self.editor_pdf_path or not self.page_order:
            messagebox.showwarning("AtenciÃ³n", "Selecciona un PDF para editar visualmente.")
            return
        if not self.selected_pages:
            messagebox.showwarning("AtenciÃ³n", "Selecciona al menos una miniatura.")
            return
        for orig_idx in self.selected_pages:
            self.page_rotations[orig_idx] = (self.page_rotations.get(orig_idx, 0) + delta) % 360
        self.render_editor_thumbnails()
        self.show_current_preview_page()
        self.set_statusbar_message("RotaciÃ³n aplicada a pÃ¡ginas seleccionadas")

    def rotate_selected_thumbnail_pages_left(self):
        self.rotate_selected_thumbnail_pages(-90)

    def rotate_selected_thumbnail_pages_right(self):
        self.rotate_selected_thumbnail_pages(90)

    def save_visual_editor_pdf(self):
        if not self.editor_pdf_path or not self.page_order:
            messagebox.showwarning("AtenciÃ³n", "Selecciona un PDF en la lista para editar visualmente.")
            return
        save_path = filedialog.asksaveasfilename(
            title="Guardar PDF editado",
            defaultextension=".pdf",
            filetypes=[("Archivos PDF", "*.pdf")],
            initialdir=str(Path(self.editor_pdf_path).parent),
            initialfile=f"{Path(self.editor_pdf_path).stem}_editado_visual.pdf"
        )
        if not save_path:
            return
        try:
            writer = PdfWriter()
            total_pages = len(self.page_order)
            self.progress["maximum"] = total_pages
            self.progress["value"] = 0
            self.progress_label.config(text="Guardando PDF editado visualmente...")
            self.root.update_idletasks()

            for idx, orig_idx in enumerate(self.page_order, start=1):
                page = self.editor_reader.pages[orig_idx]
                rotation = self.page_rotations.get(orig_idx, 0)
                if rotation:
                    if hasattr(page, "rotate"):
                        page = page.rotate(rotation)
                    elif hasattr(page, "rotate_clockwise"):
                        page = page.rotate_clockwise(rotation)
                writer.add_page(page)
                self.progress["value"] = idx

            with open(save_path, "wb") as f:
                writer.write(f)

            self.progress_label.config(text="Proceso completado.")
            self.set_statusbar_message("PDF editado guardado correctamente")
            messagebox.showinfo("Ã‰xito", f"PDF guardado en:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el PDF editado:\n{e}")

    # -------------------------------------------------
    # Temp files / clear list
    # -------------------------------------------------
    def clear_temp_files(self):
        for temp_file in self.temp_pdf_files:
            try:
                if Path(temp_file).exists():
                    Path(temp_file).unlink()
            except Exception:
                pass
        self.temp_pdf_files.clear()

    def clear_list(self):
        if not self.files:
            return
        if messagebox.askyesno("Confirmar", "Â¿Quieres limpiar toda la lista?"):
            self.files.clear()
            self.clear_file_info_cache()
            self.refresh_listbox()
            self.progress["value"] = 0
            self.progress_label.config(text="")
            self.clear_temp_files()
            self.hide_tooltip()
            self.clear_preview()
            self.set_statusbar_message("Lista limpiada")

    # -------------------------------------------------
    # PDF/Image helpers
    # -------------------------------------------------
    def image_to_pdf(self, image_path):
        return pdf_tools.image_to_pdf(image_path, self.temp_pdf_files)

    def append_source_to_writer(self, writer, file_path):
        pdf_tools.append_source_to_writer(writer, file_path, self.temp_pdf_files)

    def ask_page_range(self, max_pages, title="Rango de pÃ¡ginas"):
        text = simpledialog.askstring(title, f"Escribe pÃ¡ginas o rangos (1-{max_pages}).\nEjemplo: 1,3,5-8")
        if text is None:
            return None
        text = text.strip()
        if not text:
            return None
        pages = set()
        try:
            for part in text.split(","):
                part = part.strip()
                if "-" in part:
                    start, end = part.split("-", 1)
                    start = int(start.strip())
                    end = int(end.strip())
                    if start > end:
                        start, end = end, start
                    for p in range(start, end + 1):
                        if 1 <= p <= max_pages:
                            pages.add(p)
                else:
                    p = int(part)
                    if 1 <= p <= max_pages:
                        pages.add(p)
            return sorted(pages)
        except Exception:
            messagebox.showerror("Error", "Rango de pÃ¡ginas invÃ¡lido.")
            return None

    # -------------------------------------------------
    # Project / merge tools
    # -------------------------------------------------
    def save_project(self):
        if not self.files:
            messagebox.showwarning("AtenciÃ³n", "No hay archivos en la lista.")
            return
        save_path = filedialog.asksaveasfilename(
            title="Guardar proyecto",
            defaultextension=".json",
            filetypes=[("Proyecto JSON", "*.json")],
            initialdir=self.config_data.get("last_save_folder", str(Path.home())),
            initialfile="proyecto_mergemasterpdf.json"
        )
        if not save_path:
            return
        project_data = {
            "name": self.output_name_var.get().strip() or "PDF_UNIDO",
            "files": self.files,
            "open_pdf_after_merge": self.open_pdf_var.get(),
            "open_folder_after_merge": self.open_folder_var.get(),
            "theme": self.current_theme
        }
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(project_data, f, indent=4, ensure_ascii=False)
            self.set_statusbar_message("Proyecto guardado")
            messagebox.showinfo("Ã‰xito", f"Proyecto guardado en:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el proyecto:\n{e}")

    def load_project(self):
        project_path = filedialog.askopenfilename(
            title="Cargar proyecto",
            filetypes=[("Proyecto JSON", "*.json")],
            initialdir=self.config_data.get("last_open_folder", str(Path.home()))
        )
        if not project_path:
            return
        try:
            with open(project_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            loaded_files, missing_files = [], []
            for file_path in data.get("files", []):
                if Path(file_path).exists():
                    loaded_files.append(str(Path(file_path).resolve()))
                else:
                    missing_files.append(file_path)
            self.files = loaded_files
            self.clear_file_info_cache()
            self.output_name_var.set(data.get("name", "PDF_UNIDO"))
            self.open_pdf_var.set(data.get("open_pdf_after_merge", True))
            self.open_folder_var.set(data.get("open_folder_after_merge", False))
            theme = data.get("theme", self.current_theme)
            if theme in {"dark", "light"}:
                self.current_theme = theme
                self.apply_theme()
            self.refresh_listbox()
            self.clear_preview()
            if missing_files:
                messagebox.showwarning("Proyecto cargado parcialmente", "Algunos archivos no se encontraron:\n\n" + "\n".join(missing_files[:10]))
            else:
                self.set_statusbar_message("Proyecto cargado")
                messagebox.showinfo("Ã‰xito", "Proyecto cargado correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cargar el proyecto:\n{e}")

    def load_last_session(self):
        if not self.config_data.get("restore_last_session", True):
            self.refresh_listbox()
            return
        session_files = []
        for file_path in self.config_data.get("last_session_files", []):
            if Path(file_path).exists() and self.is_supported_file(file_path):
                session_files.append(str(Path(file_path).resolve()))
        if session_files:
            self.files = session_files
            self.refresh_listbox()
            self.set_statusbar_message("Ultima sesion restaurada")
        else:
            self.refresh_listbox()

    def merge_files(self):
        if not self.files:
            messagebox.showwarning("AtenciÃ³n", "Agrega al menos un archivo.")
            return
        output_name = self.sanitize_filename(self.output_name_var.get().strip())
        initial_save_dir = self.config_data.get("last_save_folder", str(Path.home()))
        save_path = filedialog.asksaveasfilename(
            title="Guardar PDF unido",
            defaultextension=".pdf",
            filetypes=[("Archivos PDF", "*.pdf")],
            initialdir=initial_save_dir,
            initialfile=f"{output_name}.pdf"
        )
        if not save_path:
            return
        total_files = len(self.files)
        self.progress["maximum"] = total_files
        self.progress["value"] = 0
        self.progress_label.config(text="Iniciando proceso...")
        self.root.update_idletasks()
        self.clear_temp_files()
        try:
            pdf_tools.merge_sources(self.files, save_path, self.temp_pdf_files, self.update_progress)
            save_folder = str(Path(save_path).parent)
            self.config_data["last_save_folder"] = save_folder
            self.save_config()
            self.progress_label.config(text="Proceso completado.")
            self.set_statusbar_message("PDF unido correctamente")
            messagebox.showinfo("Ã‰xito", f"PDF generado correctamente:\n{save_path}")
            if self.open_pdf_var.get():
                self.open_file(save_path)
            if self.open_folder_var.get():
                self.open_folder(save_folder)
        except Exception as e:
            messagebox.showerror("Error", f"OcurriÃ³ un error al unir los archivos:\n{e}")
            self.progress_label.config(text="OcurriÃ³ un error durante el proceso.")
        finally:
            self.clear_temp_files()

    def combine_by_name(self):
        if not self.files:
            messagebox.showwarning("AtenciÃ³n", "Agrega al menos un archivo.")
            return
        output_folder = filedialog.askdirectory(
            title="Selecciona la carpeta donde guardar los grupos combinados",
            initialdir=self.config_data.get("last_save_folder", str(Path.home()))
        )
        if not output_folder:
            return
        groups = {}
        for file_path in self.files:
            key = self.build_group_key(file_path)
            groups.setdefault(key, []).append(file_path)
        if not groups:
            messagebox.showwarning("AtenciÃ³n", "No se pudieron generar grupos.")
            return
        total_groups = len(groups)
        self.progress["maximum"] = total_groups
        self.progress["value"] = 0
        self.progress_label.config(text="Comenzando combinaciÃ³n por nombre...")
        self.root.update_idletasks()
        self.clear_temp_files()
        generated_files = []
        try:
            for group_index, (group_name, group_files) in enumerate(sorted(groups.items()), start=1):
                writer = PdfWriter()
                for file_path in sorted(group_files, key=lambda x: Path(x).name.lower()):
                    self.append_source_to_writer(writer, file_path)
                output_file = Path(output_folder) / f"{self.sanitize_filename(group_name)}.pdf"
                with open(output_file, "wb") as f:
                    writer.write(f)
                generated_files.append(str(output_file))
                self.progress["value"] = group_index
                self.progress_label.config(text=f"Generando {group_index} de {total_groups}: {Path(output_file).name}")
            self.config_data["last_save_folder"] = str(Path(output_folder))
            self.save_config()
            self.progress_label.config(text="CombinaciÃ³n por nombre completada.")
            self.set_statusbar_message("CombinaciÃ³n por nombre completada")
            messagebox.showinfo("Ã‰xito", f"Se generaron {len(generated_files)} archivo(s) en:\n{output_folder}")
            if self.open_folder_var.get():
                self.open_folder(output_folder)
            elif self.open_pdf_var.get() and len(generated_files) == 1:
                self.open_file(generated_files[0])
        except Exception as e:
            messagebox.showerror("Error", f"OcurriÃ³ un error al combinar por nombre:\n{e}")
            self.progress_label.config(text="OcurriÃ³ un error durante la combinaciÃ³n por nombre.")
        finally:
            self.clear_temp_files()

    def split_pdf(self):
        initial_dir = self.config_data.get("last_open_folder", str(Path.home()))
        pdf_path = filedialog.askopenfilename(title="Selecciona el PDF que quieres separar", filetypes=[("Archivos PDF", "*.pdf")], initialdir=initial_dir)
        if not pdf_path:
            return
        output_folder = filedialog.askdirectory(title="Selecciona la carpeta donde guardar las pÃ¡ginas", initialdir=str(Path(pdf_path).parent))
        if not output_folder:
            return
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            self.progress["maximum"] = total_pages
            self.progress["value"] = 0
            self.progress_label.config(text="Iniciando separaciÃ³n de PDF...")
            self.root.update_idletasks()
            base_name = self.sanitize_filename(Path(pdf_path).stem)
            pdf_tools.split_pdf_pages(
                pdf_path,
                output_folder,
                lambda index: f"{base_name}_pagina_{index}.pdf",
                self.update_progress
            )
            self.progress_label.config(text="SeparaciÃ³n completada.")
            self.config_data["last_open_folder"] = str(Path(pdf_path).parent)
            self.config_data["last_save_folder"] = str(output_folder)
            self.save_config()
            self.set_statusbar_message("PDF separado correctamente")
            if messagebox.askyesno("Ã‰xito", f"PDF separado correctamente en:\n{output_folder}\n\nÂ¿Quieres abrir la carpeta?"):
                self.open_folder(output_folder)
        except Exception as e:
            messagebox.showerror("Error", f"OcurriÃ³ un error al separar el PDF:\n{e}")
            self.progress_label.config(text="OcurriÃ³ un error durante la separaciÃ³n.")

    def extract_pdf_pages(self):
        pdf_path = filedialog.askopenfilename(
            title="Selecciona el PDF",
            filetypes=[("Archivos PDF", "*.pdf")],
            initialdir=self.config_data.get("last_open_folder", str(Path.home()))
        )
        if not pdf_path:
            return
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            pages_to_extract = self.ask_page_range(total_pages, "Extraer paginas")
            if pages_to_extract is None:
                return
            save_path = filedialog.asksaveasfilename(
                title="Guardar PDF extraido",
                defaultextension=".pdf",
                filetypes=[("Archivos PDF", "*.pdf")],
                initialdir=str(Path(pdf_path).parent),
                initialfile=f"{Path(pdf_path).stem}_extraido.pdf"
            )
            if not save_path:
                return
            self.progress["maximum"] = len(pages_to_extract)
            self.progress["value"] = 0
            self.progress_label.config(text="Extrayendo paginas...")
            self.root.update_idletasks()
            pdf_tools.extract_pages(pdf_path, pages_to_extract, save_path, self.update_progress)
            self.config_data["last_open_folder"] = str(Path(pdf_path).parent)
            self.config_data["last_save_folder"] = str(Path(save_path).parent)
            self.save_config()
            self.progress_label.config(text="Proceso completado.")
            self.set_statusbar_message("Paginas extraidas correctamente")
            messagebox.showinfo("Exito", f"PDF guardado en:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron extraer las paginas:\n{e}")

    def compress_pdf(self):
        if not FITZ_AVAILABLE:
            messagebox.showwarning("Aviso", "La compresion requiere PyMuPDF instalado.")
            return
        pdf_path = filedialog.askopenfilename(
            title="Selecciona el PDF",
            filetypes=[("Archivos PDF", "*.pdf")],
            initialdir=self.config_data.get("last_open_folder", str(Path.home()))
        )
        if not pdf_path:
            return
        save_path = filedialog.asksaveasfilename(
            title="Guardar PDF comprimido",
            defaultextension=".pdf",
            filetypes=[("Archivos PDF", "*.pdf")],
            initialdir=str(Path(pdf_path).parent),
            initialfile=f"{Path(pdf_path).stem}_comprimido.pdf"
        )
        if not save_path:
            return
        try:
            self.progress["maximum"] = 1
            self.progress["value"] = 0
            self.progress_label.config(text="Comprimiendo PDF...")
            self.root.update_idletasks()
            original_size, new_size, saved = pdf_tools.compress_pdf(pdf_path, save_path)
            self.progress["value"] = 1
            self.config_data["last_open_folder"] = str(Path(pdf_path).parent)
            self.config_data["last_save_folder"] = str(Path(save_path).parent)
            self.save_config()
            self.progress_label.config(text="Proceso completado.")
            self.set_statusbar_message("PDF comprimido correctamente")
            messagebox.showinfo(
                "Exito",
                "PDF guardado en:\n"
                f"{save_path}\n\n"
                f"Original: {self.format_file_size(original_size)}\n"
                f"Nuevo: {self.format_file_size(new_size)}\n"
                f"Ahorro: {self.format_file_size(saved)}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo comprimir el PDF:\n{e}")

    def export_pdf_to_images(self):
        if not FITZ_AVAILABLE:
            messagebox.showwarning("Aviso", "Exportar imagenes requiere PyMuPDF instalado.")
            return
        pdf_path = filedialog.askopenfilename(
            title="Selecciona el PDF",
            filetypes=[("Archivos PDF", "*.pdf")],
            initialdir=self.config_data.get("last_open_folder", str(Path.home()))
        )
        if not pdf_path:
            return
        output_folder = filedialog.askdirectory(
            title="Selecciona la carpeta donde guardar las imagenes",
            initialdir=str(Path(pdf_path).parent)
        )
        if not output_folder:
            return
        dpi = simpledialog.askinteger("Calidad", "DPI de salida (150 recomendado, 300 alta calidad):", minvalue=72, maxvalue=600, initialvalue=150)
        if dpi is None:
            return
        try:
            base_name = self.sanitize_filename(Path(pdf_path).stem)
            self.progress["maximum"] = 1
            self.progress["value"] = 0
            self.progress_label.config(text="Exportando paginas como imagenes...")
            self.root.update_idletasks()
            total_pages = pdf_tools.export_pdf_to_images(pdf_path, output_folder, base_name, dpi, self.update_progress)
            self.config_data["last_open_folder"] = str(Path(pdf_path).parent)
            self.config_data["last_save_folder"] = str(Path(output_folder))
            self.save_config()
            self.progress_label.config(text="Exportacion completada.")
            self.set_statusbar_message("PDF exportado a imagenes")
            if messagebox.askyesno("Exito", f"Se exportaron {total_pages} imagen(es) en:\n{output_folder}\n\nQuieres abrir la carpeta?"):
                self.open_folder(output_folder)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar el PDF a imagenes:\n{e}")

    def delete_pdf_pages(self):
        pdf_path = filedialog.askopenfilename(title="Selecciona el PDF", filetypes=[("Archivos PDF", "*.pdf")], initialdir=self.config_data.get("last_open_folder", str(Path.home())))
        if not pdf_path:
            return
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            pages_to_remove = self.ask_page_range(total_pages, "Eliminar pÃ¡ginas")
            if pages_to_remove is None:
                return
            save_path = filedialog.asksaveasfilename(
                title="Guardar PDF resultante",
                defaultextension=".pdf",
                filetypes=[("Archivos PDF", "*.pdf")],
                initialdir=str(Path(pdf_path).parent),
                initialfile=f"{Path(pdf_path).stem}_sin_paginas.pdf"
            )
            if not save_path:
                return
            pages_to_remove_zero = {p - 1 for p in pages_to_remove}
            writer = PdfWriter()
            kept_pages = [i for i in range(total_pages) if i not in pages_to_remove_zero]
            self.progress["maximum"] = max(len(kept_pages), 1)
            self.progress["value"] = 0
            self.progress_label.config(text="Eliminando pÃ¡ginas...")
            self.root.update_idletasks()
            count = 0
            for i in range(total_pages):
                if i not in pages_to_remove_zero:
                    writer.add_page(reader.pages[i])
                    count += 1
                    self.progress["value"] = count
                    self.root.update_idletasks()
            with open(save_path, "wb") as f:
                writer.write(f)
            self.progress_label.config(text="Proceso completado.")
            self.set_statusbar_message("PÃ¡ginas eliminadas correctamente")
            messagebox.showinfo("Ã‰xito", f"PDF guardado en:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron eliminar las pÃ¡ginas:\n{e}")

    def rotate_pdf_pages(self):
        pdf_path = filedialog.askopenfilename(title="Selecciona el PDF", filetypes=[("Archivos PDF", "*.pdf")], initialdir=self.config_data.get("last_open_folder", str(Path.home())))
        if not pdf_path:
            return
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            pages_to_rotate = self.ask_page_range(total_pages, "Rotar pÃ¡ginas")
            if pages_to_rotate is None:
                return
            degrees = simpledialog.askinteger("RotaciÃ³n", "Escribe grados de rotaciÃ³n (90, 180, 270):", minvalue=90, maxvalue=270)
            if degrees not in {90, 180, 270}:
                messagebox.showwarning("AtenciÃ³n", "Solo se permiten 90, 180 o 270 grados.")
                return
            save_path = filedialog.asksaveasfilename(
                title="Guardar PDF rotado",
                defaultextension=".pdf",
                filetypes=[("Archivos PDF", "*.pdf")],
                initialdir=str(Path(pdf_path).parent),
                initialfile=f"{Path(pdf_path).stem}_rotado.pdf"
            )
            if not save_path:
                return
            pages_to_rotate_zero = {p - 1 for p in pages_to_rotate}
            writer = PdfWriter()
            self.progress["maximum"] = total_pages
            self.progress["value"] = 0
            self.progress_label.config(text="Rotando pÃ¡ginas...")
            self.root.update_idletasks()
            for i in range(total_pages):
                page = reader.pages[i]
                if i in pages_to_rotate_zero:
                    if hasattr(page, "rotate"):
                        page = page.rotate(degrees)
                    elif hasattr(page, "rotate_clockwise"):
                        page = page.rotate_clockwise(degrees)
                writer.add_page(page)
                self.progress["value"] = i + 1
                self.root.update_idletasks()
            with open(save_path, "wb") as f:
                writer.write(f)
            self.progress_label.config(text="Proceso completado.")
            self.set_statusbar_message("PÃ¡ginas rotadas correctamente")
            messagebox.showinfo("Ã‰xito", f"PDF guardado en:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron rotar las pÃ¡ginas:\n{e}")

    def reorder_pdf_pages(self):
        pdf_path = filedialog.askopenfilename(title="Selecciona el PDF", filetypes=[("Archivos PDF", "*.pdf")], initialdir=self.config_data.get("last_open_folder", str(Path.home())))
        if not pdf_path:
            return
        try:
            reader = PdfReader(pdf_path)
            total_pages = len(reader.pages)
            order_text = simpledialog.askstring(
                "Reordenar pÃ¡ginas",
                f"El PDF tiene {total_pages} pÃ¡ginas.\nEscribe el nuevo orden separado por comas.\nEjemplo: 3,1,2\nPuedes usar todas las pÃ¡ginas una sola vez."
            )
            if order_text is None:
                return
            order = [int(x.strip()) for x in order_text.split(",") if x.strip()]
            if len(order) != total_pages:
                messagebox.showwarning("AtenciÃ³n", "Debes indicar exactamente todas las pÃ¡ginas una sola vez.")
                return
            if sorted(order) != list(range(1, total_pages + 1)):
                messagebox.showwarning("AtenciÃ³n", "El orden debe incluir todas las pÃ¡ginas del 1 al total, sin repetir.")
                return
            save_path = filedialog.asksaveasfilename(
                title="Guardar PDF reordenado",
                defaultextension=".pdf",
                filetypes=[("Archivos PDF", "*.pdf")],
                initialdir=str(Path(pdf_path).parent),
                initialfile=f"{Path(pdf_path).stem}_reordenado.pdf"
            )
            if not save_path:
                return
            writer = PdfWriter()
            self.progress["maximum"] = total_pages
            self.progress["value"] = 0
            self.progress_label.config(text="Reordenando pÃ¡ginas...")
            self.root.update_idletasks()
            for idx, page_number in enumerate(order, start=1):
                writer.add_page(reader.pages[page_number - 1])
                self.progress["value"] = idx
                self.root.update_idletasks()
            with open(save_path, "wb") as f:
                writer.write(f)
            self.progress_label.config(text="Proceso completado.")
            self.set_statusbar_message("PÃ¡ginas reordenadas correctamente")
            messagebox.showinfo("Ã‰xito", f"PDF guardado en:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudieron reordenar las pÃ¡ginas:\n{e}")

    # -------------------------------------------------
    # Close
    # -------------------------------------------------
    def on_close(self):
        try:
            self.save_config()
            self.clear_temp_files()
        finally:
            self.root.destroy()

    def show_features(self):
        messagebox.showinfo(
            "Resumen de funciones",
            "MergeMasterPDF\n\n"
            "Funciones disponibles:\n"
            "â€¢ Agregar PDFs e imÃ¡genes\n"
            "â€¢ Agregar carpetas completas\n"
            "â€¢ Unir y guardar PDFs\n"
            "â€¢ Combinar PDFs por nombre\n"
            "â€¢ Separar PDF por pÃ¡ginas\n"
            "â€¢ Eliminar pÃ¡ginas de un PDF\n"
            "â€¢ Rotar pÃ¡ginas de un PDF\n"
            "â€¢ Reordenar pÃ¡ginas de un PDF\n"
            "â€¢ Vista previa de PDF e imÃ¡genes\n"
            "â€¢ Miniaturas de pÃ¡ginas\n"
            "â€¢ Guardar y cargar proyectos\n"
            "â€¢ Tema oscuro / claro"
        )

    def show_shortcuts(self):
        messagebox.showinfo(
            "Atajos de teclado",
            "Atajos y acciones rÃ¡pidas:\n\n"
            "â€¢ Alt + arrastrar: reordenar archivos en la lista\n"
            "â€¢ Doble click en archivo: abrir archivo seleccionado\n"
            "â€¢ Ctrl + click: selecciÃ³n mÃºltiple\n"
            "â€¢ Shift + click: selecciÃ³n por rango\n"
            "â€¢ Click derecho: menÃº contextual\n\n"
            "Si el preview tiene zoom habilitado:\n"
            "â€¢ Ctrl + rueda del mouse: acercar o alejar"
        )

    def show_about(self):
        messagebox.showinfo(
            "Acerca de MergeMasterPDF",
            f"{APP_NAME}\n\n"
            f"VersiÃ³n: {APP_VERSION}\n\n"
            "AplicaciÃ³n de escritorio para organizar y editar PDFs.\n\n"
            "Autor: Alan Juarez"
    )

def main():
    root = TkinterDnD.Tk()
    app = PDFMergerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
