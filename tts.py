import pyttsx3
import threading

# Initialize shared TTS engine and control flags
tts_engine = pyttsx3.init()
tts_lock = threading.Lock()
tts_stop_event = threading.Event()
current_tts_thread = None

# Voice preference hints for language matching
VOICE_HINTS = {
    'en': ['David', 'Zira'],
    'ja': ['Haruka', 'Japanese'],
    'zh': ['Huihui', 'Chinese', 'ZH-CN'],
    'zh-tw': ['Tracy', 'ZH-TW', 'Chinese'],
    'ko': ['Heami', 'Korean']
}

def find_voice_for_lang(engine, lang_code):
    hints = VOICE_HINTS.get(lang_code, [])
    for voice in engine.getProperty('voices'):
        if any(h.lower() in voice.name.lower() or h.lower() in voice.id.lower() for h in hints):
            return voice.id
    return None

def speak_text(text, lang_code='en'):
    global current_tts_thread, tts_stop_event

    def tts_worker():
        with tts_lock:
            if tts_stop_event.is_set():
                return
            voice_id = find_voice_for_lang(tts_engine, lang_code)
            if voice_id:
                tts_engine.setProperty('voice', voice_id)
                print(f"[TTS] Using voice: {voice_id}")
            else:
                print(f"[TTS] No matching voice for {lang_code}, using default.")

            tts_engine.say(text)
            try:
                tts_engine.runAndWait()
            except RuntimeError:
                print("[TTS] Stopped before completion.")
            tts_engine.stop()

    # Stop any ongoing playback
    if current_tts_thread and current_tts_thread.is_alive():
        tts_stop_event.set()
        tts_engine.stop()
        current_tts_thread.join()

    # Start new playback
    tts_stop_event.clear()
    current_tts_thread = threading.Thread(target=tts_worker, daemon=True)
    current_tts_thread.start()
