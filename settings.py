"""The app's settings: one place, loaded once, stored in the per-user data folder.

    settings.load()                    # once, at startup (get() also loads lazily)
    settings.get("auto_copy")          # cheap in-memory read, safe from any thread
    settings.update(auto_tts=True)     # validate, keep in memory, write to disk

The file is settings.json inside Qt's AppDataLocation:
    Windows  C:/Users/<you>/AppData/Roaming/MultiLangOCR/
    macOS    ~/Library/Application Support/MultiLangOCR/
Keys this version doesn't know about are kept when saving, so a newer or older
version of the app never wipes them.
"""
import json
import os
import sys
import threading
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QStandardPaths

from resources import app_dir

APP_NAME = "MultiLangOCR"
SETTINGS_FILE = "settings.json"
LEGACY_FILE = "config.json"  # older versions kept this next to the code

# Option+Q types a character on a Mac, so the non-Windows defaults use Ctrl+Alt.
_HOTKEYS_WINDOWS = {"ocr_hotkey": "alt+q", "tts_hotkey": "alt+w"}
_HOTKEYS_OTHER = {"ocr_hotkey": "ctrl+alt+q", "tts_hotkey": "ctrl+alt+w"}

DEFAULTS = {
    "auto_copy": True,
    "auto_tts": False,
    "prefer_ja_over_zh": False,
    "welcome_message": True,
    **(_HOTKEYS_WINDOWS if sys.platform == "win32" else _HOTKEYS_OTHER),
}

_lock = threading.RLock()
_values = None  # set by load()


def data_dir():
    """Per-user folder for settings (created on demand)."""
    # Always set it: QApplication defaults the name to the executable ("Python"
    # when run from source), which would give a differently named folder.
    QCoreApplication.setApplicationName(APP_NAME)
    path = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation))
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path():
    return data_dir() / SETTINGS_FILE


def _read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        print(f"[Settings] Could not read {path}: {e}")
        return None
    if not isinstance(data, dict):
        print(f"[Settings] Ignoring {path}: not a JSON object")
        return None
    return data


def _clean(data, fallback=None):
    """Merge `data` over the defaults, replacing wrong-typed values.

    A bad value falls back to the matching entry of `fallback` (the current
    settings, when updating) or else to the default.
    """
    fallback = fallback or {}
    merged = dict(data)
    for key, default in DEFAULTS.items():
        keep = fallback.get(key, default)
        value = data.get(key, keep)
        if not isinstance(value, type(default)):
            print(f"[Settings] Ignoring invalid {key}={value!r}, using {keep!r}")
            value = keep
        if isinstance(value, str):
            value = value.strip() or keep
        merged[key] = value
    return merged


def load():
    """Read the settings file into memory (once). Returns a copy of the values."""
    global _values
    with _lock:
        if _values is None:
            path = settings_path()
            data = _read_json(path)
            if data is None and not path.exists():
                # First run of this version: pick up a config.json from an older one.
                data = _read_json(Path(app_dir()) / LEGACY_FILE)
                if data is not None:
                    print(f"[Settings] Imported {LEGACY_FILE} from the previous version")
            _values = _clean(data or {})
            if not path.exists():
                _save()
        return dict(_values)


def get(key):
    with _lock:
        if _values is None:
            load()
        return _values.get(key, DEFAULTS.get(key))


def update(**changes):
    """Change one or more settings and write the file."""
    with _lock:
        if _values is None:
            load()
        _values.update(_clean({**_values, **changes}, fallback=_values))
        _save()


def reset(keys=None):
    """Put the given settings (default: all of them) back to their defaults."""
    update(**{k: DEFAULTS[k] for k in (keys or DEFAULTS)})


def _save():
    path = settings_path()
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_values, f, indent=4, ensure_ascii=False)
        os.replace(tmp, path)  # atomic: a crash mid-write can't leave a broken file
    except OSError as e:
        print(f"[Settings] Could not save {path}: {e}")
