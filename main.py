import sys
import pyperclip
import json
import os
import threading
import ctypes
import time
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle, QWidget
from PyQt6.QtCore import QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QAction

# Make sure these imports are correct based on your file structure
from selector import RegionSelector
from ocr import extract_text_with_lang
from tts import speak_text
from ui import FlashOverlay
from hotkeys import setup_hotkeys
from configui import launch_config_ui


if sys.platform == "win32":
    import ctypes
    myappid = "com.xelane.ocrapp.1.0"  # Replace with your own unique string
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

recent_history = []
MAX_HISTORY = 20

temp_last_text = ""
temp_last_lang = "en" # Changed default to 'en' from 'eng' for consistency with EasyOCR/langdetect

overlay = tray = selector = main_invoker = config_window = None

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

    text, lang = extract_text_with_lang(img_array)

    final_output_text = text

    print(f"OCR Result: {final_output_text}")
    if final_output_text:
        temp_last_text = final_output_text
        temp_last_lang = lang

        settings = load_app_settings()
        if settings.get("auto_copy", True):
            pyperclip.copy(text)
        if overlay:
            overlay.display_text(final_output_text)
        if settings.get("auto_tts", False):
            threading.Thread(target=speak_text, args=(text, lang), daemon=True).start()


        recent_history.insert(0, {"text": final_output_text, "lang": lang})
        if config_window and config_window.isVisible():
            config_window.history = recent_history
            config_window.load_history()

        if len(recent_history) > MAX_HISTORY:
            recent_history.pop()

def tts_callback():
    if temp_last_text:
        speak_text(temp_last_text, temp_last_lang)

def load_app_settings():
    defaults = {
        "auto_copy": True,
        "auto_tts": False,
        "auto_start": False
    }
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                data = json.load(f)
                return {
                    "auto_copy": data.get("auto_copy", defaults["auto_copy"]),
                    "auto_tts": data.get("auto_tts", defaults["auto_tts"]),
                    "auto_start": data.get("auto_start", defaults["auto_start"])
                }
    except Exception as e:
        print(f"Failed to load app settings: {e}")
    return defaults

class TrayApp:
    def __init__(self, app):
        self.tray_icon = QSystemTrayIcon()
        self.menu = QMenu()

        icon_path = "icon.ico"
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("MultiLangOCR is running. Right-click for options.")

        # Keep actions alive as attributes
        self.open_action = QAction("Open MultiLangOCR")
        self.open_action.triggered.connect(self.open_main_window)
        self.menu.addAction(self.open_action)

        self.menu.addSeparator()

        self.exit_action = QAction("Exit")
        self.exit_action.triggered.connect(QApplication.quit)
        self.menu.addAction(self.exit_action)

        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()

    def open_main_window(self):
        global temp_last_text, temp_last_lang, config_window, recent_history
        if config_window is None or not config_window.isVisible():
            from configui import launch_config_ui
            config_window = launch_config_ui(recent_history)
            config_window.show()
        else:
            config_window.raise_()
            config_window.activateWindow()
        
    def cleanup(self):
        self.tray_icon.hide()
        self.tray_icon.deleteLater()
        QApplication.processEvents()
        time.sleep(0.05)  # slight delay helps
        refresh_tray_area()
    
def refresh_tray_area():
    hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
    if hwnd:
        ctypes.windll.user32.InvalidateRect(hwnd, None, True)


def main():
    global overlay, tray, selector, main_invoker
    print("Starting app...")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    main_invoker = MainThreadInvoker()
    overlay = FlashOverlay()
    overlay.hide()

    tray_controller = TrayApp(app)  # Important: keep reference to TrayApp instance
    
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
    app.aboutToQuit.connect(tray_controller.cleanup)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()