# MultiLangOCR

A lightweight Windows desktop utility that lets you:
- Use a global hotkey to capture a screen region
- Extract multilingual text via OCR (English, Japanese, Chinese Simplified, Chinese Traditional)
- Automatically copy to clipboard
- Play back with TTS
- Configurable settings

### Setup

For NVIDIA users:
```bash
pip install -r requirements.txt
```
Non-NVIDIA users cannot use hardware acceleration and will have to use their CPU:
```bash
pip install -r requirements-cpu.txt
```

### Run with:
```bash
python main.py
```

### Default Hotkeys
- Alt+Q → OCR scan
- Alt+W → TTS playback
