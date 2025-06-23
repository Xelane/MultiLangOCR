import keyboard
import threading
import re

HOTKEY_PATTERN = r'^(?:(?:ctrl|alt|shift)\+)*(?:[a-z0-9])$'

def is_valid_hotkey(hotkey: str) -> bool:
    return re.match(HOTKEY_PATTERN, hotkey.lower()) is not None

def setup_hotkeys(ocr_hotkey, ocr_callback, tts_hotkey, tts_callback):
    if not is_valid_hotkey(ocr_hotkey) or not is_valid_hotkey(tts_hotkey):
        print(
            "[Hotkeys] Invalid hotkey format. Use combinations like ctrl+q, alt+f, ctrl+alt+shift+k"
        )
        return

    print(f"[Hotkeys] Registering OCR hotkey: {ocr_hotkey}")
    print(f"[Hotkeys] Registering TTS hotkey: {tts_hotkey}")

    keyboard.add_hotkey(ocr_hotkey, lambda: threading.Thread(target=ocr_callback).start())
    keyboard.add_hotkey(tts_hotkey, lambda: threading.Thread(target=tts_callback).start())
