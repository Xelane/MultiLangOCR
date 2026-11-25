# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller recipe for Windows and macOS.   Build:  pyinstaller packaging/MultiLangOCR.spec

Always a one-DIRECTORY build (never --onefile): a one-file build unpacks ~300 MB
(Qt, onnxruntime, OCR models) to a temp folder on every launch.

    Windows  dist/MultiLangOCR/MultiLangOCR.exe
    macOS    dist/MultiLangOCR.app   (menu-bar app: no Dock icon)
"""
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))  # SPECPATH is provided by PyInstaller
sys.path.insert(0, ROOT)
from version import VERSION  # noqa: E402

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"


def path(*parts):
    return os.path.join(ROOT, *parts)


datas = [
    (path("icon.ico"), "."),
    (path("assets", "tray_template.png"), "assets"),
    (path("assets", "tray_template@2x.png"), "assets"),
    (path("assets", "selftest.png"), "assets"),
]
datas += collect_data_files("rapidocr")  # the OCR models (.onnx) and its YAML config
datas += collect_data_files("opencc")    # Simplified/Traditional conversion dictionaries

hiddenimports = collect_submodules("rapidocr")  # some engines are imported from config strings
if IS_MAC:
    hiddenimports += ["pynput.keyboard._darwin", "pynput.mouse._darwin"]
if IS_WIN:
    hiddenimports += [
        "pynput.keyboard._win32", "pynput.mouse._win32",
        "pyttsx3.drivers", "pyttsx3.drivers.sapi5", "comtypes", "comtypes.client",
    ]

a = Analysis(
    [path("main.py")],
    pathex=[ROOT],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "IPython", "notebook"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MultiLangOCR",
    console=False,  # windowed: no console window
    icon=path("icon.ico") if IS_WIN else path("assets", "icon.icns"),
    upx=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MultiLangOCR",
)

if IS_MAC:
    app = BUNDLE(
        coll,
        name="MultiLangOCR.app",
        icon=path("assets", "icon.icns"),
        bundle_identifier="io.github.xelane.multilangocr",
        version=VERSION,
        info_plist={
            "CFBundleName": "MultiLangOCR",
            "CFBundleDisplayName": "MultiLangOCR",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "LSUIElement": True,  # menu-bar only: no Dock icon, no app-switcher entry
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "14.0",  # the PyQt6 / numpy wheels need macOS 14
            "NSHumanReadableCopyright": "MultiLangOCR",
        },
    )
