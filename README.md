# OCR+TTS Desktop Utility

A lightweight Windows desktop utility that lets you:
- Use a global hotkey to capture a screen region
- Extract multilingual text via OCR (English, Japanese, Chinese, Korean)
- Automatically copy to clipboard
- Play back with TTS (Edge-tts)

### Features
- Global hotkeys for OCR and TTS
- Auto-language detection
- Optional auto-TTS playback
- Minimal GUI with scan history

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