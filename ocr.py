import os
import logging
import numpy as np
import cv2
from paddleocr import PaddleOCR
import platform
import paddleocr
print("[DEBUG] PaddleOCR version:", paddleocr.__version__)

logging.getLogger('ppocr').setLevel(logging.ERROR)

LANGUAGES = {
    'en': 'en',
    'ja': 'japan',
    'zh-cn': 'ch',
    'zh-tw': 'chinese_cht',
    #'ko': 'korean'
}

# Model download path
if platform.system() == "Windows":
    PADDLE_MODELS_DIR = os.path.join(os.path.expanduser('~'), '.paddlex', 'official_models')
else:
    PADDLE_MODELS_DIR = os.path.join(os.path.expanduser('~'), '.paddlex', 'official_models')

ocr_readers = {}
for common_code, paddle_lang_tag in LANGUAGES.items():
    print(f"[OCR] Loading model for {common_code} (Paddle tag: {paddle_lang_tag})...")
    try:
        reader_instance = PaddleOCR(
            lang=paddle_lang_tag,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            ocr_version="PP-OCRv5"
        )
        ocr_readers[common_code] = reader_instance
        print(f"[OCR] Loaded: {common_code} reader successfully.")
    except Exception as e:
        print(f"[OCR] Failed to load {common_code} reader: {e}")

if not ocr_readers:
    raise SystemExit("CRITICAL ERROR: No PaddleOCR readers could be loaded.")

def extract_text_with_lang(img_bgr):
    if not isinstance(img_bgr, np.ndarray) or img_bgr.size == 0:
        print("[OCR] Invalid image input.")
        return "", "en"

    debug_dir = "debug_ocr"
    os.makedirs(debug_dir, exist_ok=True)
    cv2.imwrite(os.path.join(debug_dir, "debug_input_to_ocr.png"), img_bgr)

    best_text, best_lang, best_conf = "", "en", 0.0

    for lang_code, reader in ocr_readers.items():
        try:
            result_list = reader.predict(img_bgr)
            if not result_list:
                continue
            #print(f"[DEBUG] result type for {lang_code}:", type(result_list[0]))
            #print(f"[DEBUG] result content:", result_list[0])

            ocr_result = result_list[0]
            texts = ocr_result["rec_texts"]
            scores = ocr_result["rec_scores"]

            #print(f"[OCR] Raw result for {lang_code}: {texts}, scores: {scores}")

            filtered = [(t.strip(), s) for t, s in zip(texts, scores) if t.strip()]
            if not filtered:
                continue

            text, confs = zip(*filtered)
            avg_conf = sum(confs) / len(confs)
            full_text = "\n".join(text)

            print(f"[OCR] {lang_code} avg conf: {avg_conf:.2f}")
            bonus = min(len(full_text) / 1000.0, 0.1)
            adjusted_conf = avg_conf + bonus

            if adjusted_conf > best_conf:
                best_conf = adjusted_conf
                best_text = full_text
                best_lang = lang_code

        except Exception as e:
            print(f"[OCR] Error for {lang_code}: {e}")
            continue

    print(f"[OCR] Final Best Result: Language='{best_lang}', Confidence={best_conf:.2f}")
    return best_text, best_lang if best_text else ("", "en")
