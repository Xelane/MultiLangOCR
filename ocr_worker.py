"""Runs OCR on a background thread so the UI stays responsive.

    runner = OcrRunner()
    runner.finished.connect(on_result)   # on_result(text, lang), main thread
    runner.submit(img_bgr)               # returns immediately

One long-lived worker thread handles jobs one at a time. `busy` is True from
submit() until `finished` fires, so callers can refuse overlapping scans.
"""
from PyQt6.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from ocr import extract_text_with_lang


class _Worker(QObject):
    done = pyqtSignal(str, str)

    @pyqtSlot(object)
    def run(self, img_bgr):
        try:
            text, lang = extract_text_with_lang(img_bgr)
        except Exception as e:  # never leave the caller waiting forever
            print(f"[OCR] Worker error: {e}")
            text, lang = "", "en"
        self.done.emit(text, lang)


class OcrRunner(QObject):
    _submit = pyqtSignal(object)    # main thread -> worker thread (queued)
    finished = pyqtSignal(str, str)  # text, lang ("" if nothing was found)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.busy = False
        self._thread = QThread()
        self._worker = _Worker()
        self._worker.moveToThread(self._thread)
        self._submit.connect(self._worker.run)
        self._worker.done.connect(self._on_done)
        self._thread.start()

    def submit(self, img_bgr):
        self.busy = True
        self._submit.emit(img_bgr)

    def _on_done(self, text, lang):
        self.busy = False
        self.finished.emit(text, lang)

    def shutdown(self, timeout_ms=3000):
        self._thread.quit()
        self._thread.wait(timeout_ms)
