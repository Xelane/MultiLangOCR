import logging
import numpy as np
import unicodedata
from paddleocr import PaddleOCR
import paddle
import paddleocr
from utils import load_app_settings
from opencc import OpenCC

print("[DEBUG] PaddleOCR version:", paddleocr.__version__)
logging.getLogger('ppocr').setLevel(logging.ERROR)

# Initialize PaddleOCR
if not paddle.device.get_device().startswith("gpu"):
    print("[WARNING] Running on CPU. For better performance, install the GPU version of PaddlePaddle.")
ocr = PaddleOCR(
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    ocr_version="PP-OCRv5",
)

# --- Script-level language detection ---

def detect_unicode_script(text):
    has_hiragana = has_katakana = has_cjk = has_hangul = has_latin = False
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
    return "en"

def is_kanji_only(text):
    for ch in text:
        if not ch.strip():
            continue
        try:
            name = unicodedata.name(ch)
            if any(tok in name for tok in ("HIRAGANA", "KATAKANA", "HANGUL", "LATIN")):
                return False
        except ValueError:
            continue
    return True

def is_traditional_chinese(text):
    cc = OpenCC('t2s')  # Traditional → Simplified
    return cc.convert(text) != text

# --- OCR + Language Wrapper ---

def extract_text_with_lang(img_bgr):
    if not isinstance(img_bgr, np.ndarray) or img_bgr.size == 0:
        print("[OCR] Invalid image input.")
        return "", "en"

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

        if detected_lang == "zh":
            if is_traditional_chinese(full_text):
                print("[OCR] Chinese text appears Traditional → using zh-tw")
                detected_lang = "zh-tw"
            else:
                print("[OCR] Chinese text appears Simplified → using zh")

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
