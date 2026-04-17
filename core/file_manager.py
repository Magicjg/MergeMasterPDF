from pathlib import Path
import re


SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def normalize_path(path_str):
    return str(Path(path_str).resolve())


def sanitize_filename(name, fallback="PDF_UNIDO"):
    invalid_chars = '<>:"/\\|?*'
    cleaned = "".join("_" if ch in invalid_chars else ch for ch in name)
    cleaned = cleaned.strip().rstrip(".")
    return cleaned or fallback


def is_supported_file(file_path):
    return Path(file_path).suffix.lower() in SUPPORTED_EXTENSIONS


def format_file_size(size_bytes):
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{int(size_bytes)} B"


def get_supported_files_from_folder(folder_path):
    folder = Path(folder_path)
    files = []
    for item in folder.rglob("*"):
        if item.is_file() and is_supported_file(item):
            files.append(str(item.resolve()))
    files.sort(key=natural_sort_key)
    return files


def build_group_key(file_path):
    stem = Path(file_path).stem.strip()
    patterns = [r"[\s_-]+\d+$", r"\(\d+\)$"]
    base = stem
    for pattern in patterns:
        base = re.sub(pattern, "", base).strip()
    return sanitize_filename(base or stem)


def natural_sort_key(file_path):
    name = Path(file_path).name.lower()
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", name)]
