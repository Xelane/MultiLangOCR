"""Text-to-speech.

    speak_text(text, "ja")   # returns immediately; interrupts anything still being spoken
    stop_speaking()

Both are safe to call from the Qt main thread and from any other thread.

    macOS    NSSpeechSynthesizer in-process (starts speaking in ~0.3 s); falls
             back to the `say` command, which needs ~1 s to launch each time.
             Call from the main thread (the Qt thread) - AppKit expects it.
    Windows  SAPI through pyttsx3, on one dedicated thread (any thread may call)
"""
import queue
import re
import subprocess
import sys
import threading
import time

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"


# --- macOS ---------------------------------------------------------------------

# A line of `say -v ?`:  "Eddy (Japanese (Japan)) ja_JP    # こんにちは! ..."
_VOICE_LINE = re.compile(r"^(?P<name>.+?)\s+(?P<locale>[a-z]{2,3}_[A-Za-z0-9]+)\s+#")

# Locales to try, in order, for each language code the OCR can report.
_MAC_LOCALES = {
    "en": ("en_US", "en_GB"),
    "ja": ("ja_JP",),
    "zh": ("zh_CN",),
    "zh-tw": ("zh_TW", "zh_HK"),
    "ko": ("ko_KR",),
}
# Last resort: any voice of the language, whatever the region.
_MAC_LANG_PREFIX = {"en": "en_", "ja": "ja_", "zh": "zh_", "zh-tw": "zh_", "ko": "ko_"}
_MAC_PREFERRED = {
    "en": ("Samantha", "Alex", "Daniel", "Karen", "Moira"),
    "ja": ("Kyoko", "O-Ren"),
    "zh": ("Tingting", "Ting-Ting", "Lili"),
    "zh-tw": ("Meijia", "Mei-Jia"),
    "ko": ("Yuna",),
}
# macOS ships joke voices under en_US; never pick these just because they sort first.
_MAC_NOVELTY = {
    "Albert", "Bad News", "Bahh", "Bells", "Boing", "Bubbles", "Cellos", "Fred",
    "Good News", "Jester", "Junior", "Organ", "Ralph", "Superstar", "Trinoids",
    "Whisper", "Wobble", "Zarvox", "Kathy",
}


def parse_say_voices(output):
    """`say -v ?` output -> [(voice name, locale)]."""
    voices = []
    for line in output.splitlines():
        match = _VOICE_LINE.match(line)
        if match:
            voices.append((match.group("name"), match.group("locale")))
    return voices


def choose_voice(voices, lang):
    """Pick the best installed voice for `lang`, or None to use the system default."""
    stages = [[v for v in voices if v[1] == locale] for locale in _MAC_LOCALES.get(lang, ())]
    if lang in _MAC_LANG_PREFIX:
        stages.append([v for v in voices if v[1].startswith(_MAC_LANG_PREFIX[lang])])
    for pool in stages:
        for preferred in _MAC_PREFERRED.get(lang, ()):
            for name, _ in pool:
                if name == preferred or name.startswith(preferred + " ("):
                    return name
        for name, _ in pool:
            if name not in _MAC_NOVELTY:
                return name
    return None


class _SaySpeaker:
    """Fallback: the `say` command in a subprocess, killed to interrupt."""

    def __init__(self):
        self._lock = threading.Lock()
        self._proc = None
        self._voices = None

    def _installed_voices(self):
        if self._voices is None:
            try:
                out = subprocess.run(["say", "-v", "?"], capture_output=True, text=True,
                                     timeout=10, check=True).stdout
            except (OSError, subprocess.SubprocessError) as e:
                print(f"[TTS] Could not list voices: {e}")
                out = ""
            self._voices = parse_say_voices(out)
        return self._voices

    def warm_up(self):
        with self._lock:
            self._installed_voices()

    def speak(self, text, lang):
        with self._lock:
            self._stop_locked()
            voice = choose_voice(self._installed_voices(), lang)
            if voice:
                print(f"[TTS] Using voice: {voice}")
            else:
                print(f"[TTS] No voice installed for '{lang}', using the system default.")
            # Arguments go straight to the process (no shell); "--" keeps text
            # that starts with a dash from being read as an option.
            cmd = ["say"] + (["-v", voice] if voice else []) + ["--", text]
            try:
                self._proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError as e:
                print(f"[TTS] Could not run say: {e}")

    def stop(self):
        with self._lock:
            self._stop_locked()

    def _stop_locked(self):
        proc, self._proc = self._proc, None
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()


class _CocoaSpeaker:
    """One long-lived NSSpeechSynthesizer: no process to launch per request."""

    START_SETTLE_SECONDS = 0.1

    def __init__(self):
        from AppKit import NSSpeechSynthesizer  # ImportError if PyObjC/AppKit is unavailable
        self._ns = NSSpeechSynthesizer
        self._lock = threading.Lock()
        self._voices = None     # [(name, locale)] in the shape choose_voice() expects
        self._ids = {}          # voice name -> NSSpeechSynthesizer voice identifier
        self._synth = None
        self._voice_id = object()  # sentinel: no voice chosen yet
        self._started_at = 0.0

    def _installed_voices(self):
        if self._voices is None:
            voices = []
            for identifier in self._ns.availableVoices():
                attrs = self._ns.attributesForVoice_(identifier)
                name = str(attrs.get("VoiceName") or "")
                locale = str(attrs.get("VoiceLocaleIdentifier") or "")
                if name and locale:
                    voices.append((name, locale))
                    self._ids.setdefault(name, str(identifier))
            self._voices = voices
        return self._voices

    def warm_up(self):
        with self._lock:  # about 1 s: call from a background thread
            self._installed_voices()

    def speak(self, text, lang):
        with self._lock:
            name = choose_voice(self._installed_voices(), lang)
            identifier = self._ids.get(name) if name else None
            if self._synth is None:
                self._synth = self._ns.alloc().init()
            self._stop_synth()
            if identifier != self._voice_id:
                self._synth.setVoice_(identifier)  # None = the system default voice
                self._voice_id = identifier
            if name:
                print(f"[TTS] Using voice: {name}")
            else:
                print(f"[TTS] No voice installed for '{lang}', using the system default.")
            self._started_at = time.monotonic()
            if not self._synth.startSpeakingString_(text):
                print("[TTS] The speech synthesizer could not start speaking.")

    def stop(self):
        with self._lock:
            if self._synth is not None:
                self._stop_synth()

    def _stop_synth(self):
        # macOS silently drops a stop that arrives within ~50 ms of the start
        # (the speech then plays on), so let a just-started speech get going first.
        wait = self.START_SETTLE_SECONDS - (time.monotonic() - self._started_at)
        if wait > 0:
            time.sleep(wait)
        self._synth.stopSpeaking()


def _make_mac_speaker():
    try:
        return _CocoaSpeaker()
    except Exception as e:  # AppKit missing, or removed in a future macOS
        print(f"[TTS] NSSpeechSynthesizer unavailable ({e}); using the 'say' command.")
        return _SaySpeaker()


# --- Windows -------------------------------------------------------------------

# Substrings of Windows voice names / ids, best match first.
_WIN_VOICE_HINTS = {
    "en": ["Zira", "David", "Mark", "Hazel", "English"],
    "ja": ["Haruka", "Ayumi", "Ichiro", "Sayaka", "Japanese"],
    "zh": ["Huihui", "Yaoyao", "Kangkang", "ZH-CN", "Chinese (Simplified"],
    "zh-tw": ["Hanhan", "Yating", "Zhiwei", "Tracy", "ZH-TW", "Chinese (Traditional"],
    "ko": ["Heami", "Korean"],
}


def find_windows_voice(voices, lang):
    """voices: objects with .name and .id. Hints are tried in priority order."""
    for hint in _WIN_VOICE_HINTS.get(lang, []):
        hint = hint.lower()
        for voice in voices:
            if hint in voice.name.lower() or hint in voice.id.lower():
                return voice.id
    return None


class _WindowsSpeaker:
    """All pyttsx3/SAPI work happens on one thread, which owns the engine.

    SAPI objects must stay on the thread that created them, so other threads
    never touch the engine. To interrupt, speak()/stop() bump a generation
    number; the engine's word callback (running on the speech thread) notices
    it is out of date and calls engine.stop(), and jobs that were superseded
    before they started are skipped.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._generation = 0
        self._current = 0
        self._jobs = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="tts", daemon=True)
        self._thread.start()

    def warm_up(self):
        self._jobs.put(None)  # creates the engine ahead of the first real request

    def speak(self, text, lang):
        with self._lock:
            self._generation += 1
            generation = self._generation
        self._jobs.put((generation, text, lang))

    def stop(self):
        with self._lock:
            self._generation += 1

    def _run(self):
        import pyttsx3  # only needed (and installed) on Windows

        engine = None
        while True:
            job = self._jobs.get()
            try:
                if engine is None:
                    engine = pyttsx3.init()
                    engine.connect("started-word", self._make_word_callback(engine))
                if job is None:
                    continue
                generation, text, lang = job
                if generation != self._generation:
                    continue  # superseded while it waited in the queue
                self._current = generation
                voice_id = find_windows_voice(engine.getProperty("voices"), lang)
                if voice_id:
                    engine.setProperty("voice", voice_id)
                    print(f"[TTS] Using voice: {voice_id}")
                else:
                    print(f"[TTS] No matching voice for '{lang}', using the default.")
                engine.say(text)
                engine.runAndWait()
            except Exception as e:
                print(f"[TTS] Speech failed: {e}")
                engine = None  # start from a fresh engine next time

    def _make_word_callback(self, engine):
        def on_word(**_):  # pyttsx3 passes name=, location=, length=
            if self._current != self._generation:
                engine.stop()  # a newer request (or stop()) arrived: cut this one short
        return on_word


# --- Other platforms -----------------------------------------------------------

class _UnsupportedSpeaker:
    def warm_up(self):
        pass

    def speak(self, text, lang):
        print("[TTS] Text-to-speech is not supported on this platform.")

    def stop(self):
        pass


# --- Public API ----------------------------------------------------------------

_speaker = None
_speaker_lock = threading.Lock()


def _get_speaker():
    global _speaker
    with _speaker_lock:
        if _speaker is None:
            if IS_MAC:
                _speaker = _make_mac_speaker()
            elif IS_WIN:
                _speaker = _WindowsSpeaker()
            else:
                _speaker = _UnsupportedSpeaker()
        return _speaker


def speak_text(text, lang_code="en"):
    """Speak `text` in the voice for `lang_code`, interrupting current speech."""
    text = (text or "").strip()
    if text:
        _get_speaker().speak(text, lang_code)


def stop_speaking():
    if _speaker is not None:
        _speaker.stop()


def warm_up():
    """Do the slow one-time setup (voice list / engine) ahead of the first request."""
    _get_speaker().warm_up()
