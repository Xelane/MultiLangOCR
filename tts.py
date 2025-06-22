import pyttsx3

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
    try:
        engine = pyttsx3.init()  # re-init every time
        # [FIX] Set volume to the maximum (1.0)
        engine.setProperty('volume', 1.0)
        voice_id = find_voice_for_lang(engine, lang_code)

        if voice_id:
            engine.setProperty('voice', voice_id)
            print(f"[TTS] Using voice: {voice_id}")
        else:
            print(f"[TTS] No matching voice for {lang_code}, using default.")

        engine.say(text)
        engine.runAndWait()
        engine.stop()  # clean exit
    except Exception as e:
        print(f"[TTS] Error: {e}")
