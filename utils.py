import json
import os

def load_app_settings():
    defaults = {
        "auto_copy": True,
        "auto_tts": False,
        "auto_start": False,
        "prefer_ja_over_zh": False
    }
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                data = json.load(f)
                return {
                    "auto_copy": data.get("auto_copy", True),
                    "auto_tts": data.get("auto_tts", False),
                    "auto_start": data.get("auto_start", False),
                    "prefer_ja_over_zh": data.get("prefer_ja_over_zh", False)
                }
    except Exception as e:
        print(f"[UTIL] Failed to load app settings: {e}")
    return defaults
