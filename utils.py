import json
import os

DEFAULT_SETTINGS = {
    "auto_copy": True,
    "auto_tts": False,
    "auto_start": False,
    "prefer_ja_over_zh": False
}

def load_app_settings(config_path="config.json"):
    if not os.path.exists(config_path):
        return DEFAULT_SETTINGS.copy()

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                key: data.get(key, default)
                for key, default in DEFAULT_SETTINGS.items()
            }
    except Exception as e:
        print(f"[UTIL] Failed to load config from {config_path}: {e}")
        return DEFAULT_SETTINGS.copy()
