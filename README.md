# MultiLangOCR

A desktop tool for extracting text from screen regions using OCR, with automatic clipboard copying and text-to-speech playback. Works on Windows and macOS.

## Screenshots

<p align="center">
  <img src="./screenshots/app.png" alt="App">
  <br>
  <img src="./screenshots/scan.png" alt="Scan">
</p>

## Features

- Global hotkey screen capture
- OCR for English, Japanese and Chinese (Simplified/Traditional), including vertical Japanese. Korean is not supported
- Automatic clipboard copying
- Text-to-speech playback
- Configurable settings
- Runs offline

## Download

Get the zip for your system from the [Releases page](../../releases/latest), unzip it and run it. No Python needed.

- **Windows** 10 or 11. The first time, SmartScreen may warn: click **More info**, then **Run anyway**.
- **macOS** 14 or newer, Apple Silicon. See below.

### macOS first launch

The app is unsigned, so macOS blocks it at first:

1. Drag `MultiLangOCR.app` to Applications and open it.
2. Open **System Settings > Privacy & Security**, find the message about MultiLangOCR and click **Open Anyway**.
3. Allow these when asked (it opens the right Settings page for you): **Screen & System Audio Recording** (then quit and reopen the app), **Accessibility** and **Input Monitoring**.

If scans or hotkeys stop working after you update the app, remove MultiLangOCR from those three lists and add it again.

## Usage

**Default Hotkeys:**
- Alt+Q → OCR scan (macOS: Ctrl+Option+Q)
- Alt+W → TTS playback (macOS: Ctrl+Option+W)

Drag a box around the text; Esc cancels. You can also pick **Scan now** from the tray / menu bar icon, which is also where the preferences are.

To change the hotkeys, quit the app and edit `ocr_hotkey` and `tts_hotkey` in `settings.json` (Windows: `%APPDATA%\MultiLangOCR`, macOS: `~/Library/Application Support/MultiLangOCR`), for example `"ctrl+shift+f9"`.

Text-to-speech uses the voices installed on your computer. If a language is silent, install a voice for it in your system settings.

## Run from source

```bash
pip install -r requirements.txt
python main.py
```

Python 3.12 recommended.

## Build

```bash
pip install -r requirements-build.txt
pyinstaller packaging/MultiLangOCR.spec
```

To publish a release, set the version in `version.py`, then push a matching tag (for example `v2.0.0`). GitHub Actions builds and attaches both apps.

## Dependencies

- RapidOCR (PP-OCR models) for text recognition
- OpenCC for Chinese character conversion
- pynput for hotkeys
- PyQt6 for the GUI

## Licence

GPL-3.0, see [LICENSE](LICENSE).
