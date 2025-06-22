# hotkeys.py
import keyboard
import threading
import re

# Valid hotkey pattern: ctrl+key, shift+key, ctrl+shift+key
def is_valid_hotkey(hotkey):
    pattern = r'^(?:(?:ctrl|alt|shift)\+)*(?:[a-z0-9])$'
    return re.match(pattern, hotkey.lower())

def setup_hotkeys(ocr_hotkey, ocr_callback, tts_hotkey, tts_callback):
    if not is_valid_hotkey(ocr_hotkey) or not is_valid_hotkey(tts_hotkey):
        print("Invalid hotkey format. Use combinations of ctrl, alt, shift with a key (a-z, 0-9).")
        print("Example valid formats: ctrl+q, shift+a, alt+f, ctrl+shift+z, ctrl+alt+c, ctrl+alt+shift+k")
        return

    print(f"Registering OCR hotkey: {ocr_hotkey}")
    print(f"Registering TTS hotkey: {tts_hotkey}")

    keyboard.add_hotkey(ocr_hotkey, lambda: threading.Thread(target=ocr_callback).start())
    keyboard.add_hotkey(tts_hotkey, lambda: threading.Thread(target=tts_callback).start())
