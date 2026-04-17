from tkinter import ttk


THEMES = {
    "light": {
        "bg_main": "#eef2f7",
        "bg_panel": "#ffffff",
        "bg_card": "#ffffff",
        "bg_list": "#f8fafc",
        "fg_text": "#0f172a",
        "fg_title": "#0b1220",
        "accent": "#2563eb",
        "accent_soft": "#dbeafe",
        "danger": "#dc2626",
        "warning": "#d97706",
        "success": "#16a34a",
        "secondary": "#7c3aed",
        "muted": "#64748b",
        "entry_bg": "#ffffff",
        "entry_border": "#dbe2ea",
        "tooltip_bg": "#111111",
        "tooltip_fg": "white",
        "summary_fg": "#1d4ed8",
        "progress_trough": "#dbe2ea",
        "drop_border": "#bfdbfe",
        "button_text": "#ffffff",
        "card_border": "#e5e7eb",
        "scrollbar_bg": "#e2e8f0",
        "preview_bg": "#f1f5f9",
        "thumb_selected": "#dbeafe",
        "thumb_normal": "#ffffff",
    },
    "dark": {
        "bg_main": "#111827",
        "bg_panel": "#1f2937",
        "bg_card": "#1f2937",
        "bg_list": "#111827",
        "fg_text": "#f9fafb",
        "fg_title": "#ffffff",
        "accent": "#60a5fa",
        "accent_soft": "#1e3a8a",
        "danger": "#ef4444",
        "warning": "#f59e0b",
        "success": "#22c55e",
        "secondary": "#8b5cf6",
        "muted": "#94a3b8",
        "entry_bg": "#0f172a",
        "entry_border": "#334155",
        "tooltip_bg": "#020617",
        "tooltip_fg": "white",
        "summary_fg": "#93c5fd",
        "progress_trough": "#334155",
        "drop_border": "#3b82f6",
        "button_text": "#ffffff",
        "card_border": "#334155",
        "scrollbar_bg": "#334155",
        "preview_bg": "#0b1220",
        "thumb_selected": "#1e3a8a",
        "thumb_normal": "#1f2937",
    },
}


def get_theme_colors(theme_name):
    return THEMES.get(theme_name, THEMES["dark"])


def configure_styles():
    style = ttk.Style()
    style.theme_use("default")
    return style


def configure_progressbar(style, colors):
    style.configure(
        "Custom.Horizontal.TProgressbar",
        troughcolor=colors["progress_trough"],
        background=colors["accent"],
        bordercolor=colors["progress_trough"],
        lightcolor=colors["accent"],
        darkcolor=colors["accent"],
    )
