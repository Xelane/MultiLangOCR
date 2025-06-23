# MultiLangOCR

A lightweight Windows desktop utility that lets you:
- Use a global hotkey to capture a screen region
- Extract multilingual text via OCR (English, Japanese, Chinese Simplified, Chinese Traditional)
- Automatically copy to clipboard
- Play back with TTS
- Configurable settings

### Setup

NVIDIA users:
```bash
pip install --pre paddlepaddle-gpu -i https://www.paddlepaddle.org.cn/packages/nightly/cu118/
pip install -r requirements.txt
```

Non-NVIDIA (CPU) users:
```bash
pip install paddlepaddle
pip install -r requirements-cpu.txt
```

### Run launch.bat to run the program

Alternatively run:
```bash
python main.py
```

### Default Hotkeys
- Alt+Q → OCR scan
- Alt+W → TTS playback
