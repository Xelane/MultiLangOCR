"""OCR backend using RapidOCR (PP-OCR models on onnxruntime).

No PaddlePaddle install needed: the default PP-OCRv6 model (Chinese,
Traditional Chinese, Japanese, English) ships inside the rapidocr wheel,
so `pip install rapidocr onnxruntime` is all it takes and it bundles
cleanly with PyInstaller.

Public interface is unchanged from the PaddleOCR version:
    extract_text_with_lang(img_bgr) -> (text, lang)
"""
import logging
import threading
import unicodedata

import numpy as np
from opencc import OpenCC
from rapidocr import RapidOCR

from utils import load_app_settings

logging.getLogger("RapidOCR").setLevel(logging.WARNING)

# Lines below this confidence are dropped as likely noise.
MIN_LINE_CONFIDENCE = 0.5

# Pixels of background colour added around every capture before detection.
DETECT_MARGIN_PX = 20

_engine = None
_engine_lock = threading.Lock()
_t2s = OpenCC("t2s")  # created once, not on every scan


def get_engine():
    """Create the OCR engine on first use (thread-safe)."""
    global _engine
    with _engine_lock:
        if _engine is None:
            _engine = RapidOCR(params={
                # The rotation classifier is for upside-down document photos;
                # screen captures don't need it, and skipping it saves time.
                "Global.use_cls": False,
                # RapidOCR's default (736) scales any image whose short side is
                # smaller than that UP to 736 px. A tight crop of a few words
                # becomes a blurry 20x enlargement and the detector finds
                # nothing. 64 is what PaddleOCR used; short text then works.
                "Det.limit_side_len": 64,
            })
        return _engine


def warm_up():
    """Load models and run one tiny inference so the first real scan is fast.

    Call this from a background thread at startup.
    """
    blank = np.full((32, 100, 3), 255, dtype=np.uint8)
    get_engine()(blank)


# --- Script-level language detection ---

def _script_of(ch):
    try:
        name = unicodedata.name(ch)
    except ValueError:
        return None
    if name.startswith(("IDEOGRAPHIC", "FULLWIDTH")) or "CJK SYMBOL" in name:
        return "CJK PUNCT"
    for script in ("HIRAGANA", "KATAKANA", "HANGUL", "CJK UNIFIED", "LATIN"):
        if script in name:
            return script
    return None


def detect_unicode_script(text):
    scripts = {_script_of(ch) for ch in text if ch.strip()}
    if "HIRAGANA" in scripts or "KATAKANA" in scripts:
        return "ja"
    if "HANGUL" in scripts:
        return "ko"
    if "CJK UNIFIED" in scripts:
        return "zh"
    return "en"


def is_kanji_only(text):
    return not any(
        _script_of(ch) in ("HIRAGANA", "KATAKANA", "HANGUL", "LATIN")
        for ch in text if ch.strip()
    )


def has_non_japanese_hanzi(text):
    """True if the text contains Chinese characters that Japanese doesn't
    use (e.g. Simplified 东 们 这, and some Traditional forms). These can't
    be encoded in Shift-JIS (cp932), which makes a cheap, dependency-free test.
    """
    for ch in text:
        if _script_of(ch) == "CJK UNIFIED":
            try:
                ch.encode("cp932")
            except UnicodeEncodeError:
                return True
    return False


def is_traditional_chinese(text):
    return _t2s.convert(text) != text


def _is_cjk_char(ch):
    return _script_of(ch) in ("HIRAGANA", "KATAKANA", "CJK UNIFIED", "HANGUL", "CJK PUNCT")


def join_lines(lines, lang):
    """Join OCR lines. CJK text wrapped across lines shouldn't get newlines
    inserted mid-sentence, so join CJK-to-CJK breaks with nothing.
    """
    if lang == "en":
        return "\n".join(lines)
    out = lines[0]
    for line in lines[1:]:
        if out and line and _is_cjk_char(out[-1]) and _is_cjk_char(line[0]):
            out += line
        else:
            out += "\n" + line
    return out


def group_into_lines(pieces):
    """Merge OCR boxes that sit on the same visual line.

    pieces: [(text, box)] in detector order, box being 4 (x, y) corners or None.
    The detector sometimes splits one line into several boxes ("Hello" and
    "world"); those must become "Hello world", not two lines. Returns one string
    per visual line. Tall, narrow boxes (vertical text) are never merged.
    """
    lines = []  # each: {"top", "bottom", "items": [(left, text)]}; top is None if unmergeable
    for text, box in pieces:
        if box is None:
            lines.append({"top": None, "bottom": None, "items": [(0.0, text)]})
            continue
        xs, ys = box[:, 0], box[:, 1]
        left, top, bottom = float(xs.min()), float(ys.min()), float(ys.max())
        horizontal = (xs.max() - xs.min()) >= (bottom - top)

        best, best_ratio = None, 0.5  # must overlap by more than half the smaller height
        if horizontal:
            for line in lines:
                if line["top"] is None:
                    continue
                overlap = min(bottom, line["bottom"]) - max(top, line["top"])
                ratio = overlap / max(1.0, min(bottom - top, line["bottom"] - line["top"]))
                if ratio > best_ratio:
                    best, best_ratio = line, ratio
        if best is None:
            lines.append({"top": top if horizontal else None, "bottom": bottom if horizontal else None,
                          "items": [(left, text)]})
        else:
            best["items"].append((left, text))

    result = []
    for line in lines:
        texts = [t for _, t in sorted(line["items"], key=lambda item: item[0])]
        joined = texts[0]
        for t in texts[1:]:
            joined += t if (_is_cjk_char(joined[-1]) and _is_cjk_char(t[0])) else " " + t
        result.append(joined)
    return result


def add_margin(img, pad=DETECT_MARGIN_PX):
    """Surround the image with its own background colour.

    The detector often finds nothing in a tightly cropped word because the
    glyphs touch the image edge. Extra margin (colour taken from the border,
    so dark themes work too) makes short selections reliable.
    """
    if img.ndim != 3:
        return img
    h, w = img.shape[:2]
    border = np.concatenate([img[0], img[-1], img[:, 0], img[:, -1]])
    out = np.empty((h + 2 * pad, w + 2 * pad, img.shape[2]), dtype=img.dtype)
    out[:] = np.median(border, axis=0)
    out[pad:pad + h, pad:pad + w] = img
    return out


# --- OCR + Language Wrapper ---

def extract_text_with_lang(img_bgr):
    if not isinstance(img_bgr, np.ndarray) or img_bgr.size == 0:
        print("[OCR] Invalid image input.")
        return "", "en"

    try:
        result = get_engine()(add_margin(img_bgr))
    except Exception as e:
        print("[OCR] Unexpected error:", e)
        return "", "en"

    texts = result.txts or ()
    scores = result.scores or ()
    boxes = result.boxes if result.boxes is not None else [None] * len(texts)
    lines = group_into_lines([
        (t.strip(), b) for t, s, b in zip(texts, scores, boxes)
        if t.strip() and s >= MIN_LINE_CONFIDENCE
    ])
    if not lines:
        print("[OCR] No confident text found.")
        return "", "en"

    raw = "".join(lines)
    detected_lang = detect_unicode_script(raw)

    settings = load_app_settings()
    if detected_lang == "zh":
        if (settings.get("prefer_ja_over_zh", False) and is_kanji_only(raw)
                and not has_non_japanese_hanzi(raw)):
            detected_lang = "ja"
        elif is_traditional_chinese(raw):
            detected_lang = "zh-tw"

    full_text = join_lines(lines, detected_lang)
    avg_conf = sum(scores) / len(scores)
    print(f"[OCR] '{full_text[:30]}' (lang={detected_lang}, conf={avg_conf:.3f})")
    return full_text, detected_lang
