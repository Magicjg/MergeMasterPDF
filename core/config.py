from pathlib import Path
import json
import os
import sys


def get_config_file(app_name, source_file):
    if getattr(sys, "frozen", False):
        appdata_root = Path(os.getenv("APPDATA") or str(Path.home()))
        return appdata_root / app_name / "config.json"
    return Path(source_file).resolve().parent / "config.json"


def get_resource_path(relative_path, source_file):
    base_path = Path(getattr(sys, "_MEIPASS", Path(source_file).resolve().parent))
    return base_path / relative_path


def load_config(config_file, defaults):
    config = defaults.copy()
    if Path(config_file).exists():
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                config.update(json.load(f))
        except Exception:
            pass
    return config


def save_config(config_file, data):
    config_path = Path(config_file)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
