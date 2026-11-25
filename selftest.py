"""`MultiLangOCR --self-test [report-file]`

Checks that this install (or a frozen PyInstaller build) can actually do its
job: load Qt, find its bundled files, read the OCR model, recognise text,
reach the speech engine and the hotkey backend. It shows no window, installs
no hotkeys and never triggers an OS permission prompt, so CI can run it on a
fresh machine. Exit code 0 means every check passed.
"""
import io
import os
import shutil
import sys
import tempfile
import traceback

from version import VERSION


def _check_qt_and_resources(context):
    from PyQt6.QtCore import QStandardPaths, qVersion
    from PyQt6.QtWidgets import QApplication

    QStandardPaths.setTestModeEnabled(True)  # never touch the real settings folder
    context["app"] = QApplication.instance() or QApplication([])
    from resources import resource_path
    missing = [name for name in ("icon.ico", "assets/tray_template.png", "assets/selftest.png") if not os.path.exists(resource_path(name))]
    if missing:
        raise FileNotFoundError(f"bundled files missing: {missing}")
    return f"Qt {qVersion()}, bundled icons found"


def _check_settings(context):
    import settings

    settings.load()
    settings.update(auto_tts=True)
    ok = settings.get("auto_tts") is True and settings.settings_path().exists()
    settings.reset()
    shutil.rmtree(settings.data_dir(), ignore_errors=True)  # the Qt test-mode folder
    if not ok:
        raise RuntimeError("settings did not round-trip")
    return str(settings.settings_path().parent)


def _check_ocr_model_bundled(context):
    import rapidocr

    models = os.path.join(os.path.dirname(rapidocr.__file__), "models")
    found = sorted(f for f in os.listdir(models) if f.endswith(".onnx"))
    if not any("det" in f for f in found) or not any("rec" in f for f in found):
        raise FileNotFoundError(f"OCR models not bundled in {models}: {found}")
    return ", ".join(found)


def _check_ocr_reads_text(context):
    from PyQt6.QtGui import QImage
    from resources import resource_path
    from selector import qimage_to_bgr
    import ocr

    # A fixed image ("Hello World 2026" / "こんにちは"), not text drawn at run time:
    # a bare test machine may have no usable fonts.
    image = QImage(resource_path("assets/selftest.png"))
    if image.isNull():
        raise FileNotFoundError("assets/selftest.png could not be loaded")
    # Also prove a result survives a stdout that cannot print Japanese (a Finder-launched
    # app has no locale): this once turned every CJK scan into "No text found".
    real_stdout = sys.stdout
    sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
    try:
        text, lang = ocr.extract_text_with_lang(qimage_to_bgr(image))
    finally:
        sys.stdout = real_stdout
    missing = [w for w in ("hello", "2026", "こんにちは") if w not in text.lower()]
    if missing:
        raise RuntimeError(f"OCR output is missing {missing}: {text!r}")
    return f"{text!r} ({lang})"


def _check_chinese_variant_data(context):
    import ocr

    if not ocr.is_traditional_chinese("漢字") or ocr.is_traditional_chinese("汉字"):
        raise RuntimeError("OpenCC conversion data is missing or wrong")
    return "OpenCC data bundled"


def _check_hotkeys(context):
    from pynput import keyboard  # loads the Windows / macOS backend

    import hotkeys

    parsed = hotkeys.parse_hotkey(hotkeys.default_hotkeys()["ocr_hotkey"])
    keyboard.Listener(on_press=lambda key: None)  # created, deliberately never started
    return f"backend {keyboard.Listener.__module__}, default scan hotkey {hotkeys.format_hotkey(parsed.text)}"


def _check_permission_probes(context):
    import permissions

    return ", ".join(f"{name}={getattr(permissions, name)()}" for name in
                     ("screen_capture_allowed", "accessibility_trusted", "input_monitoring_allowed"))


def _check_tts(context):
    import tts

    if sys.platform == "darwin":
        speaker = tts._make_mac_speaker()
        speaker.warm_up()
        voice = tts.choose_voice(getattr(speaker, "_voices", None) or [], "en")
        return f"{type(speaker).__name__}, English voice: {voice}"
    if sys.platform == "win32":
        import comtypes.client  # noqa: F401
        import pyttsx3
        import pyttsx3.drivers.sapi5  # noqa: F401
        try:
            voices = pyttsx3.init().getProperty("voices")
        except Exception as e:  # a machine with no speech voices is not a packaging error
            return f"WARNING: pyttsx3 imports fine but could not start an engine here ({e})"
        return f"SAPI via pyttsx3, {len(voices)} voices"
    return "text-to-speech not supported on this platform"


CHECKS = [
    ("qt + bundled files", _check_qt_and_resources),
    ("settings", _check_settings),
    ("OCR model files", _check_ocr_model_bundled),
    ("OCR reads text", _check_ocr_reads_text),
    ("Chinese variant data", _check_chinese_variant_data),
    ("hotkey backend", _check_hotkeys),
    ("permission probes", _check_permission_probes),
    ("text-to-speech", _check_tts),
]


def run(report_path=None):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    lines = [f"MultiLangOCR {VERSION} self-test on {sys.platform}, Python {sys.version.split()[0]}"
             + (" (frozen)" if getattr(sys, "frozen", False) else "")]
    context, failures = {}, 0
    for name, check in CHECKS:
        try:
            lines.append(f"ok    {name}: {check(context)}")
        except Exception:
            failures += 1
            lines.append(f"FAIL  {name}\n{traceback.format_exc()}")
    lines.append("RESULT: " + ("all checks passed" if not failures else f"{failures} check(s) FAILED"))
    report = "\n".join(lines) + "\n"

    if report_path is None:
        report_path = os.path.join(tempfile.gettempdir(), "multilangocr-selftest.txt")
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
    except OSError:
        pass
    print(report)  # no-op when a windowed Windows build has no console
    return 1 if failures else 0
