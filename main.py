import sys
import os
import json
import threading
import pyperclip
import ctypes
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle, QWidget
from PyQt6.QtCore import QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QIcon, QAction

from selector import RegionSelector
from ocr import extract_text_with_lang
from tts import speak_text
from ui import FlashOverlay
from hotkeys import setup_hotkeys
from configui import launch_config_ui

recent_history = []
MAX_HISTORY = 20

temp_last_text = ""
temp_last_lang = "en"

overlay = tray = selector = main_invoker = config_window = None

class MainThreadInvoker(QObject):
    show_selector_signal = pyqtSignal()

def load_hotkeys():
    default_keys = {
        "ocr_hotkey": "alt+q",
        "tts_hotkey": "alt+w"
    }
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                config = json.load(f)
                return {
                    "ocr_hotkey": config.get("ocr_hotkey", default_keys["ocr_hotkey"]),
                    "tts_hotkey": config.get("tts_hotkey", default_keys["tts_hotkey"])
                }
    except Exception as e:
        print(f"[CONFIG] Failed to load hotkeys: {e}")
    return default_keys

def _show_selector_on_main_thread():
    global selector
    if selector is None:
        selector = RegionSelector()
        selector.selection_done.connect(handle_region)
    QTimer.singleShot(100, lambda: selector.show())

def ocr_scan_callback():
    main_invoker.show_selector_signal.emit()

def tts_callback():
    if temp_last_text:
        speak_text(temp_last_text, temp_last_lang)

def load_app_settings():
    defaults = {
        "auto_copy": True,
        "auto_tts": False
    }
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                data = json.load(f)
                return {**defaults, **data}
    except Exception as e:
        print(f"[CONFIG] Failed to load app settings: {e}")
    return defaults

def handle_region(img_array):
    global temp_last_text, temp_last_lang

    if img_array is None:
        print("[OCR] No valid image selected.")
        return

    text, lang = extract_text_with_lang(img_array)
    if not text:
        return

    temp_last_text = text
    temp_last_lang = lang

    settings = load_app_settings()
    if settings.get("auto_copy", True):
        pyperclip.copy(text)
    if overlay:
        overlay.display_text(text)
    if settings.get("auto_tts", False):
        threading.Thread(target=speak_text, args=(text, lang), daemon=True).start()

    recent_history.insert(0, {"text": text, "lang": lang})
    if config_window and config_window.isVisible():
        config_window.history = recent_history
        config_window.load_history()

    if len(recent_history) > MAX_HISTORY:
        recent_history.pop()

class TrayApp:
    def __init__(self, app):
        self.tray_icon = QSystemTrayIcon()
        self.menu = QMenu()

        icon_path = "icon.ico"
        icon = QIcon(icon_path) if os.path.exists(icon_path) else app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip("MultiLangOCR is running. Right-click for options.")

        self.tray_icon.activated.connect(self.on_tray_icon_activated)

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
        global config_window
        if config_window is None or not config_window.isVisible():
            config_window = launch_config_ui(history=recent_history)
            config_window.show()
        else:
            config_window.raise_()
            config_window.activateWindow()

    def cleanup(self):
        self.tray_icon.hide()
        self.tray_icon.deleteLater()
        QApplication.processEvents()
        refresh_tray_area()

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.open_main_window()

def refresh_tray_area():
    hwnd = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
    if hwnd:
        ctypes.windll.user32.InvalidateRect(hwnd, None, True)

def main():
    global overlay, tray, selector, main_invoker
    print("Starting MultiLangOCR...")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    main_invoker = MainThreadInvoker()
    main_invoker.show_selector_signal.connect(_show_selector_on_main_thread)

    overlay = FlashOverlay()
    overlay.hide()

    tray_controller = TrayApp(app)
    overlay.display_text("MultiLangOCR is running")

    keys = load_hotkeys()
    QTimer.singleShot(0, lambda: setup_hotkeys(keys["ocr_hotkey"], ocr_scan_callback, keys["tts_hotkey"], tts_callback))

    keep_alive = QTimer()
    keep_alive.start(10000)
    keep_alive.timeout.connect(lambda: None)

    app.aboutToQuit.connect(tray_controller.cleanup)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
