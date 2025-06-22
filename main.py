import sys
import pyperclip
import json
import os
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle
from PyQt6.QtCore import QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QAction

# Make sure these imports are correct based on your file structure
from selector import RegionSelector
from ocr import extract_text_with_lang
from tts import speak_text
from ui import FlashOverlay
from hotkeys import setup_hotkeys
from config_gui import ConfigWindow


if sys.platform == "win32":
    import ctypes
    myappid = "com.xelane.ocrapp.1.0"  # Replace with your own unique string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)


temp_last_text = ""
temp_last_lang = "en" # Changed default to 'en' from 'eng' for consistency with EasyOCR/langdetect

temp_last_text = ""
overlay = tray = selector = main_invoker = None

class MainThreadInvoker(QObject):
    show_selector_signal = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)

def load_hotkeys():
    default_keys = {
        "ocr_hotkey": "alt+q",
        "tts_hotkey": "alt+w"
    }
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                config = json.load(f)
                return {
                    "ocr_hotkey": config.get("ocr_hotkey", default_keys["ocr_hotkey"]),
                    "tts_hotkey": config.get("tts_hotkey", default_keys["tts_hotkey"])
                }
        except Exception as e:
            print(f"Error loading config.json: {e}")
    return default_keys

def _show_selector_on_main_thread():
    global selector
    print("[main-thread] Preparing to show selector.")
    if selector is None:
        selector = RegionSelector()
        # Connect the signal. It now emits a numpy array directly.
        selector.selection_done.connect(handle_region)
        print("[main-thread] RegionSelector instance created and signal connected.")

    def show_selector_after_delay():
        print(f"[main-thread] Attempting to show selector. Is visible: {selector.isVisible()}")
        selector.show()
        selector.raise_()
        selector.activateWindow()
        selector.setFocus()
        print(f"[main-thread] Selector shown. Geometry: {selector.geometry()}")

    QTimer.singleShot(100, show_selector_after_delay)

def ocr_scan_callback():
    print("OCR hotkey triggered (possibly from a non-GUI thread)")
    main_invoker.show_selector_signal.emit()

def handle_region(img_array):
    global temp_last_text
    global temp_last_lang

    if img_array is None:
        print("No valid image data received from selector (selection possibly cancelled or invalid).")
        return

    text, lang = extract_text_with_lang(img_array) # This 'text' is now the full paragraph

    # --- SIMPLIFIED POST-PROCESSING / TEXT HANDLING ---
    final_output_text = text # Start with the text from OCR

    if lang == 'ja':
        # Apply the dot-to-comma correction if still needed
        original_final_output_text = final_output_text
        final_output_text = final_output_text.replace('.', '、') # Replace period with Japanese comma (tōten)
        if original_final_output_text != final_output_text:
            print(f"[OCR Post-process] Corrected dot to comma: '{original_final_output_text}' -> '{final_output_text}'")
    # --- END SIMPLIFIED ---

    print(f"OCR Result: {final_output_text}") # Print the final text
    if final_output_text: # Check the final processed text
        temp_last_text = final_output_text
        temp_last_lang = lang
        pyperclip.copy(final_output_text)
        if overlay:
            overlay.display_text(final_output_text)

def tts_callback():
    if temp_last_text:
        speak_text(temp_last_text, temp_last_lang)

class TrayApp(QSystemTrayIcon):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setIcon(QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        menu = QMenu()
        settings_action = QAction("Preferences")
        settings_action.triggered.connect(self.open_config)
        menu.addAction(settings_action)
        exit_action = QAction("Exit")
        exit_action.triggered.connect(QApplication.quit)
        menu.addAction(exit_action)
        self.setContextMenu(menu)
        self.show()
    def open_config(self):
        self.config_window = ConfigWindow()
        self.config_window.show()


def main():
    global overlay, tray, selector, main_invoker
    print("Starting app...")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    icon_path = "icon.ico"
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
        
    main_invoker = MainThreadInvoker()
    tray = TrayApp()
    overlay = FlashOverlay()
    overlay.hide()

    keys = load_hotkeys()
    main_invoker.show_selector_signal.connect(_show_selector_on_main_thread)

    def deferred_hotkey_setup():
        print("Deferred hotkey setup running...")
        setup_hotkeys(keys["ocr_hotkey"], ocr_scan_callback, keys["tts_hotkey"], tts_callback)

    QTimer.singleShot(0, deferred_hotkey_setup)

    keep_alive = QTimer()
    keep_alive.start(10000)
    keep_alive.timeout.connect(lambda: None)

    print("Running event loop...")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()