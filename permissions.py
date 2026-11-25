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

ACCESSIBILITY_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"
)
INPUT_MONITORING_SETTINGS_URL = (
    "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent"
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


def accessibility_trusted():
    """True if this process may observe keyboard events (Accessibility)."""
    if not IS_MAC:
        return True
    result = _call_bool("ApplicationServices", "AXIsProcessTrusted")
    return True if result is None else result


def input_monitoring_allowed():
    """True if this process has Input Monitoring permission (macOS 10.15+)."""
    if not IS_MAC:
        return True
    result = _call_bool("CoreGraphics", "CGPreflightListenEventAccess")
    return True if result is None else result


def hotkey_permissions_granted():
    return accessibility_trusted() and input_monitoring_allowed()


def _request_hotkey_permissions():
    """Ask macOS to show its prompts, which also lists the app in System Settings."""
    _call_bool("CoreGraphics", "CGRequestListenEventAccess")
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
        AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
    except Exception as e:  # pyobjc missing or API changed: the dialog below still explains
        print(f"[Permissions] Could not request Accessibility access: {e}")


def ensure_hotkey_permissions(parent=None):
    """Explain which macOS permissions global hotkeys still need. Returns True if none."""
    missing = []
    if not accessibility_trusted():
        missing.append(("Accessibility", ACCESSIBILITY_SETTINGS_URL))
    if not input_monitoring_allowed():
        missing.append(("Input Monitoring", INPUT_MONITORING_SETTINGS_URL))
    if not missing:
        return True

    _request_hotkey_permissions()

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Information)
    box.setWindowTitle("Permission needed for hotkeys")
    box.setText("macOS is blocking MultiLangOCR's global hotkeys.")
    box.setInformativeText(
        "In System Settings > Privacy & Security, switch MultiLangOCR on under: "
        + ", ".join(name for name, _ in missing)
        + ".\n\nHotkeys start working by themselves once that is done (if they "
        "don't, quit and reopen the app). Until then, use 'Scan now' in the "
        "menu bar icon.\n\n"
        "If you are running from source, switch on the app you launched it "
        "from (Terminal, iTerm or VS Code) instead."
    )
    buttons = {
        box.addButton(f"Open {name} Settings", QMessageBox.ButtonRole.ActionRole): url
        for name, url in missing
    }
    box.addButton(QMessageBox.StandardButton.Close)
    box.exec()
    if box.clickedButton() in buttons:
        QDesktopServices.openUrl(QUrl(buttons[box.clickedButton()]))
    return False


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
