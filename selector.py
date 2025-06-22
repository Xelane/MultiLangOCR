from PyQt6.QtWidgets import QWidget, QRubberBand, QApplication
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPixmap, QImage
from PIL import ImageGrab
from PIL.ImageQt import ImageQt
import numpy as np
import cv2


class RegionSelector(QWidget):
    selection_done = pyqtSignal(object)

    def __init__(self):
        super().__init__()

        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setWindowOpacity(1.0)

        self.origin = QPoint()
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        print("[Selector] RegionSelector initialized with specified flags.")

        self._background_pixmap = None

    def adjust_geometry_to_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            screen_rect = screen.geometry()
            self.setGeometry(screen_rect)
            print(f"[Selector] Adjusted screen geometry: {screen_rect}")
        else:
            print("Warning: No screen detected when adjusting geometry.")

    def showEvent(self, event):
        self.adjust_geometry_to_screen()

        img = ImageGrab.grab()
        qt_img = ImageQt(img)
        qimage = qt_img.copy()

        self._background_pixmap = QPixmap.fromImage(qimage)

        print("[Selector] Screenshot updated for frozen background.")
        super().showEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)

        if self._background_pixmap:
            painter.drawPixmap(self.rect(), self._background_pixmap)

        painter.fillRect(self.rect(), QColor(0, 0, 0, 50))

    def mousePressEvent(self, event):
        print(f"[Selector] mousePressEvent at {event.position().toPoint()}")
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position().toPoint()
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()

    def mouseMoveEvent(self, event):
        if not self.origin.isNull():
            self.rubber_band.setGeometry(QRect(self.origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.origin.isNull():
            local_rect = self.rubber_band.geometry()

            if local_rect.width() <= 0 or local_rect.height() <= 0:
                print("[Selector] Invalid region, cancelling.")
                self.selection_done.emit(None)
                self.close()
                return

            crop_rect_on_screen = local_rect.translated(self.pos())

            if self._background_pixmap:
                cropped_pixmap = self._background_pixmap.copy(crop_rect_on_screen)
                print(f"[Selector] Cropped Pixmap size: {cropped_pixmap.size()}")

                qimage = cropped_pixmap.toImage()

                # --- FIX START ---
                # Ensure the QImage format is something we can convert
                # If you know your screenshot will always be ARGB32, you can remove this check
                # and directly convert to ARGB32. However, this is safer.
                if qimage.format() != QImage.Format.Format_ARGB32:
                    qimage = qimage.convertToFormat(QImage.Format.Format_ARGB32)
                
                # Get the buffer from QImage
                ptr = qimage.constBits()
                
                # Calculate the correct buffer size for setsize
                buffer_size = qimage.bytesPerLine() * qimage.height()
                ptr.setsize(buffer_size) # Corrected line: Use calculated size
                
                # Create numpy array from QImage buffer
                img_array = np.array(ptr).reshape(qimage.height(), qimage.width(), 4)

                # Convert from ARGB (QImage's internal format) to RGB (for EasyOCR) # BGR for PaddleOCR
                img_for_ocr_np = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)
                # --- FIX END ---
                
                self.selection_done.emit(img_for_ocr_np)
                print(f"[Selector] Selection made: {local_rect} and image emitted.")
            else:
                print("[Selector] No background pixmap available for cropping, emitting None.")
                self.selection_done.emit(None)

            self.rubber_band.hide()
            self.origin = QPoint()
            self.close()

    def keyPressEvent(self, event):
        print(f"[Selector] keyPressEvent: {event.key()}")
        if event.key() == Qt.Key.Key_Escape:
            self.selection_done.emit(None)
            self.close()
            print("[Selector] Selector closed via Escape key.")
        super().keyPressEvent(event)