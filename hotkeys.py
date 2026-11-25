"""Global hotkeys (Windows + macOS) built on pynput.

Hotkeys are written as text such as "alt+q", "ctrl+alt+q", "ctrl+shift+f9" or
"f8". Modifiers: ctrl, alt (Option on a Mac), shift, cmd (Windows key on
Windows). The final key is a letter, a digit or F1-F20. A bare F-key is
allowed; letters and digits need at least one modifier.

Keys are matched by their physical key code, not by the character they
produce. That matters on macOS, where Option+Q types "œ" and Ctrl+Q a control
character, so matching on characters would never see a "q".

pynput calls us from its own listener thread. Nothing Qt-related happens
there: the thread only emits signals, which Qt delivers on the main thread.
"""
import re
import sys
from dataclasses import dataclass

from pynput import keyboard
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

import settings
from permissions import ensure_hotkey_permissions, hotkey_permissions_granted

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

def default_hotkeys():
    return {key: settings.DEFAULTS[key] for key in ("ocr_hotkey", "tts_hotkey")}


# --- Parsing -----------------------------------------------------------------

_MODIFIER_ALIASES = {
    "ctrl": "ctrl", "control": "ctrl",
    "alt": "alt", "option": "alt", "opt": "alt",
    "shift": "shift",
    "cmd": "cmd", "command": "cmd", "win": "cmd", "super": "cmd", "meta": "cmd",
}
_MODIFIER_ORDER = ("ctrl", "alt", "shift", "cmd")

# macOS virtual key codes for the ANSI positions of letters and digits.
_MAC_VK = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
    "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "9": 25, "7": 26,
    "8": 28, "0": 29, "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38,
    "k": 40, "n": 45, "m": 46,
}

_FKEY_RE = re.compile(r"^f([1-9]|1[0-9]|20)$")
_CHAR_RE = re.compile(r"^[a-z0-9]$")


@dataclass(frozen=True)
class Hotkey:
    text: str            # normalised, e.g. "ctrl+alt+q"
    modifiers: frozenset  # subset of {"ctrl", "alt", "shift", "cmd"}
    ident: tuple         # ("vk", code) for letters/digits, ("fkey", n) for F-keys


def _char_vk(char):
    if IS_MAC:
        return _MAC_VK[char]
    return ord(char.upper())  # Windows VK codes for 0-9 and A-Z are their ASCII codes


def parse_hotkey(text):
    """Parse hotkey text into a Hotkey. Raises ValueError with a readable reason."""
    if not isinstance(text, str) or not text.strip():
        raise ValueError("hotkey is empty")
    parts = [p.strip().lower() for p in text.split("+")]
    key_name, modifier_names = parts[-1], parts[:-1]

    modifiers = set()
    for name in modifier_names:
        if name not in _MODIFIER_ALIASES:
            raise ValueError(f"unknown modifier '{name}' (use ctrl, alt, shift, cmd)")
        modifiers.add(_MODIFIER_ALIASES[name])

    fkey = _FKEY_RE.match(key_name)
    if fkey:
        ident = ("fkey", int(fkey.group(1)))
    elif _CHAR_RE.match(key_name):
        if not modifiers:
            raise ValueError(f"'{key_name}' needs a modifier (e.g. ctrl+{key_name}), or it would block typing")
        if IS_MAC and key_name not in _MAC_VK:
            raise ValueError(f"unsupported key '{key_name}'")
        ident = ("vk", _char_vk(key_name))
    else:
        raise ValueError(f"unsupported key '{key_name}' (use a letter, a digit, or F1-F20)")

    ordered = [m for m in _MODIFIER_ORDER if m in modifiers]
    return Hotkey("+".join(ordered + [key_name]), frozenset(modifiers), ident)


def format_hotkey(text):
    """Human-friendly label, e.g. "Ctrl+Option+Q" on a Mac."""
    names = {"ctrl": "Ctrl", "alt": "Option" if IS_MAC else "Alt", "shift": "Shift",
             "cmd": "Cmd" if IS_MAC else "Win"}
    try:
        hotkey = parse_hotkey(text)
    except ValueError:
        return text
    *mods, key = hotkey.text.split("+")
    return "+".join([names[m] for m in mods] + [key.upper()])


# --- Matching pynput key events ---------------------------------------------

def _build_modifier_map():
    names = {
        "ctrl": ("ctrl", "ctrl_l", "ctrl_r"),
        "alt": ("alt", "alt_l", "alt_r"),
        "shift": ("shift", "shift_l", "shift_r"),
        "cmd": ("cmd", "cmd_l", "cmd_r"),
    }
    mapping = {}
    for modifier, attrs in names.items():
        for attr in attrs:
            key = getattr(keyboard.Key, attr, None)
            if key is not None:
                mapping[key] = modifier
    return mapping


_MODIFIER_KEYS = _build_modifier_map()
_FKEYS = {
    getattr(keyboard.Key, f"f{n}"): n for n in range(1, 21) if hasattr(keyboard.Key, f"f{n}")
}


def _classify(key):
    """Return ("mod", name), ("fkey", n), ("vk", code) or None if irrelevant."""
    if key is None:
        return None
    if key in _MODIFIER_KEYS:  # Key members are hashable; KeyCode hashes fine too
        return ("mod", _MODIFIER_KEYS[key])
    if key in _FKEYS:
        return ("fkey", _FKEYS[key])
    vk = getattr(key, "vk", None)
    return ("vk", vk) if vk is not None else None


class HotkeyMatcher:
    """Tracks held modifiers and fires a callback when a bound combo is pressed."""

    def __init__(self, bindings):
        self._bindings = list(bindings)  # [(Hotkey, callable)]
        self._modifiers = set()
        self._held = set()

    def on_press(self, key, *_):
        ident = _classify(key)
        if ident is None:
            return
        if ident[0] == "mod":
            if ident[1] not in self._modifiers:
                self._modifiers.add(ident[1])
                self._held.clear()
            return
        if ident in self._held:
            return  # auto-repeat while the key is held down
        self._held.add(ident)
        for hotkey, callback in self._bindings:
            if hotkey.ident == ident and hotkey.modifiers == self._modifiers:
                try:
                    callback()
                except Exception as e:
                    print(f"[Hotkeys] Callback failed: {e}")

    def on_release(self, key, *_):
        ident = _classify(key)
        if ident is None:
            return
        if ident[0] == "mod":
            self._modifiers.discard(ident[1])
            # macOS doesn't deliver key-up for keys pressed with Cmd held,
            # so forget held keys whenever the modifier state changes.
            self._held.clear()
        else:
            self._held.discard(ident)


# --- Qt-facing manager --------------------------------------------------------

class HotkeyManager(QObject):
    """Runs the pynput listener and re-emits hotkeys as Qt signals."""

    ocr_triggered = pyqtSignal()
    tts_triggered = pyqtSignal()

    WATCHDOG_MS = 3000

    def __init__(self, ocr_hotkey, tts_hotkey, parent=None):
        super().__init__(parent)
        self._ocr = parse_hotkey(ocr_hotkey)    # raise ValueError on bad input
        self._tts = parse_hotkey(tts_hotkey)
        if self._ocr.ident == self._tts.ident and self._ocr.modifiers == self._tts.modifiers:
            raise ValueError("the OCR and TTS hotkeys must be different")
        self._listener = None
        self._permission_prompted = False
        self._watchdog = QTimer(self)
        self._watchdog.setInterval(self.WATCHDOG_MS)
        self._watchdog.timeout.connect(self._ensure_running)

    @property
    def ocr_label(self):
        return format_hotkey(self._ocr.text)

    @property
    def tts_label(self):
        return format_hotkey(self._tts.text)

    def start(self):
        self._ensure_running()
        # The watchdog also picks up a permission granted after startup,
        # and restarts the listener if it ever dies.
        self._watchdog.start()

    def stop(self):
        self._watchdog.stop()
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _ensure_running(self):
        if self._listener is not None and self._listener.is_alive():
            return
        if not hotkey_permissions_granted():
            if not self._permission_prompted:
                self._permission_prompted = True
                ensure_hotkey_permissions()
            return

        matcher = HotkeyMatcher([
            (self._ocr, self.ocr_triggered.emit),  # emit() is safe from any thread
            (self._tts, self.tts_triggered.emit),
        ])
        self._listener = keyboard.Listener(on_press=matcher.on_press, on_release=matcher.on_release)
        self._listener.daemon = True
        self._listener.start()
        print(f"[Hotkeys] OCR: {self.ocr_label}   TTS: {self.tts_label}")
