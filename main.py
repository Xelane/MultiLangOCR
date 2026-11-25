import sys
import os
import json
import threading
import traceback
import pyperclip
import ctypes
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QStyle, QWidget
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon, QAction

from selector import RegionSelector
from ocr import warm_up
from ocr_worker import OcrRunner
from tts import speak_text
from ui import FlashOverlay
from hotkeys import HotkeyManager, default_hotkeys
from configui import launch_config_ui

recent_history = []
MAX_HISTORY = 20

temp_last_text = ""
temp_last_lang = "en"

overlay = tray = selector = hotkey_manager = ocr_runner = config_window = None

def load_hotkeys():
    default_keys = default_hotkeys()
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

def ocr_scan_callback():
    """Start a region scan. Must run on the Qt main thread."""
    global selector
    if ocr_runner and ocr_runner.busy:
        if overlay:
            overlay.display_text("Still scanning...")
        return
    if selector is None:
        selector = RegionSelector()
        selector.selection_done.connect(handle_region)
    if selector.is_active:
        return
    if overlay:
        overlay.hide()  # keep the status overlay out of the screenshot
    QTimer.singleShot(100, selector.start)

def tts_callback():
    if temp_last_text:
        # Off the main thread: speak_text can block while stopping earlier speech.
        threading.Thread(target=speak_text, args=(temp_last_text, temp_last_lang), daemon=True).start()

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
    """Selector finished: hand the image to the OCR thread."""
    if img_array is None:
        print("[OCR] No valid image selected.")
        return
    if overlay:
        overlay.display_text("Scanning...")
    ocr_runner.submit(img_array)

def handle_ocr_result(text, lang):
    """OCR finished (runs on the main thread)."""
    global temp_last_text, temp_last_lang

    if not text:
        if overlay:
            overlay.display_text("No text found")
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

        self.scan_action = QAction("Scan now")
        # Wait for the menu to finish closing so it isn't in the screenshot.
        self.scan_action.triggered.connect(lambda: QTimer.singleShot(300, ocr_scan_callback))
        self.menu.addAction(self.scan_action)

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

def _warm_up_ocr():
    try:
        warm_up()
    except Exception as e:
        print(f"[OCR] Warm-up failed: {e}")

def _log_uncaught(exc_type, exc, tb):
    # PyQt6 aborts the whole process on an uncaught exception in a slot unless
    # a custom excepthook is installed. Log it and keep the tray app alive.
    traceback.print_exception(exc_type, exc, tb)

def main():
    global overlay, tray, selector, hotkey_manager, ocr_runner
    sys.excepthook = _log_uncaught
    print("Starting MultiLangOCR...")

    # Load OCR models in the background so the first scan isn't slow.
    threading.Thread(target=_warm_up_ocr, daemon=True).start()

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    overlay = FlashOverlay()
    overlay.hide()

    ocr_runner = OcrRunner()
    ocr_runner.finished.connect(handle_ocr_result)
    app.aboutToQuit.connect(ocr_runner.shutdown)

    tray_controller = TrayApp(app)

    keys = load_hotkeys()
    try:
        hotkey_manager = HotkeyManager(keys["ocr_hotkey"], keys["tts_hotkey"])
    except ValueError as e:
        print(f"[Hotkeys] Invalid hotkey in config ({e}); using the defaults.")
        keys = default_hotkeys()
        hotkey_manager = HotkeyManager(keys["ocr_hotkey"], keys["tts_hotkey"])
    hotkey_manager.ocr_triggered.connect(ocr_scan_callback)
    hotkey_manager.tts_triggered.connect(tts_callback)
    app.aboutToQuit.connect(hotkey_manager.stop)
    QTimer.singleShot(0, hotkey_manager.start)

    overlay.display_text(f"MultiLangOCR is running - scan: {hotkey_manager.ocr_label}")
    tray_controller.tray_icon.setToolTip(
        f"MultiLangOCR - scan: {hotkey_manager.ocr_label}, read aloud: {hotkey_manager.tts_label}"
    )

    keep_alive = QTimer()
    keep_alive.start(10000)
    keep_alive.timeout.connect(lambda: None)

    app.aboutToQuit.connect(tray_controller.cleanup)
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
