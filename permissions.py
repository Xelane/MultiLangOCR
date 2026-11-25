"""OS permission checks (macOS only; every check passes on other platforms).

Uses ctypes against the system frameworks, so no pyobjc dependency.
"""
import ctypes
import sys

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QMessageBox

IS_MAC = sys.platform == "darwin"

SCREEN_RECORDING_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
)

_screen_access_requested = False


def _load_framework(name):
    try:
        return ctypes.CDLL(f"/System/Library/Frameworks/{name}.framework/{name}")
    except OSError:
        return None


def _call_bool(framework, symbol):
    """Call a no-argument C function returning bool. None if it doesn't exist."""
    lib = _load_framework(framework)
    fn = getattr(lib, symbol, None) if lib else None
    if fn is None:
        return None
    fn.restype = ctypes.c_bool
    return bool(fn())


def screen_capture_allowed():
    """True if this process may capture other apps' windows.

    Without Screen Recording permission macOS doesn't fail: capture silently
    returns only the wallpaper, which would just look like "OCR found nothing".
    """
    if not IS_MAC:
        return True
    result = _call_bool("CoreGraphics", "CGPreflightScreenCaptureAccess")
    return True if result is None else result  # None: macOS < 10.15, no permission


def ensure_screen_capture_permission(parent=None):
    """Return True if capture is allowed; otherwise explain how to fix it."""
    global _screen_access_requested
    if screen_capture_allowed():
        return True

    if not _screen_access_requested:
        # Shows the system prompt once and adds the app to the Screen
        # Recording list so the user has something to switch on.
        _screen_access_requested = True
        _call_bool("CoreGraphics", "CGRequestScreenCaptureAccess")

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle("Screen Recording permission needed")
    box.setText("macOS is blocking screen capture for MultiLangOCR.")
    box.setInformativeText(
        "Without it, scans only see your desktop wallpaper.\n\n"
        "Open System Settings > Privacy & Security > Screen & System Audio "
        "Recording, switch MultiLangOCR on, then quit and reopen it.\n\n"
        "If you are running from source, switch on the app you launched it "
        "from (Terminal, iTerm or VS Code) instead."
    )
    open_button = box.addButton("Open System Settings", QMessageBox.ButtonRole.ActionRole)
    box.addButton(QMessageBox.StandardButton.Close)
    box.exec()
    if box.clickedButton() is open_button:
        QDesktopServices.openUrl(QUrl(SCREEN_RECORDING_SETTINGS_URL))
    return False
