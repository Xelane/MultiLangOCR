import os
import logging
import numpy as np
import cv2
import unicodedata
from paddleocr import PaddleOCR
import paddleocr
from utils import load_app_settings


print("[DEBUG] PaddleOCR version:", paddleocr.__version__)
logging.getLogger('ppocr').setLevel(logging.ERROR)

ocr = PaddleOCR(
    lang="japan",  # multilingual model: en, ja, zh, ko
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    ocr_version="PP-OCRv5"
)

# Unicode-based script detection
def detect_unicode_script(text):
    has_hiragana = False
    has_katakana = False
    has_cjk = False
    has_hangul = False
    has_latin = False

    for ch in text:
        if not ch.strip():
            continue
        try:
            name = unicodedata.name(ch)
            if "HIRAGANA" in name:
                has_hiragana = True
            elif "KATAKANA" in name:
                has_katakana = True
            elif "HANGUL" in name:
                has_hangul = True
            elif "CJK UNIFIED" in name:
                has_cjk = True
            elif "LATIN" in name:
                has_latin = True
        except ValueError:
            continue

    if has_hiragana or has_katakana:
        return "ja"
    elif has_hangul:
        return "ko"
    elif has_cjk:
        return "zh"
    elif has_latin:
        return "en"
    else:
        return "en"

def is_kanji_only(text):
    for ch in text:
        if not ch.strip():
            continue
        try:
            name = unicodedata.name(ch)
            if (
                "HIRAGANA" in name
                or "KATAKANA" in name
                or "HANGUL" in name
                or "LATIN" in name
            ):
                return False  # Has other language markers
        except ValueError:
            continue
    return True  # Only CJK or symbols


def extract_text_with_lang(img_bgr):
    detected_lang = "en"  # <-- default fallback
    full_text = ""
    if not isinstance(img_bgr, np.ndarray) or img_bgr.size == 0:
        print("[OCR] Invalid image input.")
        return "", "en"

    debug_dir = "debug_ocr"
    os.makedirs(debug_dir, exist_ok=True)
    cv2.imwrite(os.path.join(debug_dir, "debug_input_to_ocr.png"), img_bgr)

    try:
        result_list = ocr.predict(img_bgr)

        if not result_list or not isinstance(result_list[0], dict):
            print("[OCR] Invalid result format:", result_list)
            return "", "en"

        ocr_result = result_list[0]
        texts = ocr_result.get("rec_texts", [])
        scores = ocr_result.get("rec_scores", [])

        if not texts or not scores or len(texts) != len(scores):
            print("[OCR] Empty or mismatched rec_texts/scores")
            return "", "en"

        filtered = [(t.strip(), s) for t, s in zip(texts, scores) if t.strip()]
        if not filtered:
            return "", "en"

        lines, confs = zip(*filtered)
        full_text = "\n".join(lines)
        avg_conf = sum(confs) / len(confs)

        detected_lang = detect_unicode_script(full_text)
        
        settings = load_app_settings()
        if detected_lang == "zh" and settings.get("prefer_ja_over_zh", False):
            if is_kanji_only(full_text):
                print("[OCR] Kanji-only text detected — overriding zh → ja due to user preference")
                detected_lang = "ja"


        print(f"[OCR] Detected text: '{full_text[:30]}' (lang={detected_lang}, conf={avg_conf:.3f})")
        return full_text, detected_lang

    except Exception as e:
        print("[OCR] Unexpected error:", e)
        return "", "en"
