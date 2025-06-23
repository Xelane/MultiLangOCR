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
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.origin = QPoint()
        self.rubber_band = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self._background_pixmap = None

    def adjust_geometry_to_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())

    def showEvent(self, event):
        self.adjust_geometry_to_screen()
        img = ImageGrab.grab()
        qimage = ImageQt(img).copy()
        self._background_pixmap = QPixmap.fromImage(qimage)
        self.activateWindow()
        self.setFocus()
        super().showEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._background_pixmap:
            painter.drawPixmap(self.rect(), self._background_pixmap)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 50))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.origin = event.position().toPoint()
            self.rubber_band.setGeometry(QRect(self.origin, QSize()))
            self.rubber_band.show()

    def mouseMoveEvent(self, event):
        if not self.origin.isNull():
            rect = QRect(self.origin, event.position().toPoint()).normalized()
            self.rubber_band.setGeometry(rect)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self.origin.isNull():
            return

        rect = self.rubber_band.geometry()
        if rect.width() <= 0 or rect.height() <= 0:
            self.selection_done.emit(None)
            self.close()
            return

        if self._background_pixmap:
            cropped = self._background_pixmap.copy(rect.translated(self.pos())).toImage()
            if cropped.format() != QImage.Format.Format_ARGB32:
                cropped = cropped.convertToFormat(QImage.Format.Format_ARGB32)

            ptr = cropped.constBits()
            ptr.setsize(cropped.bytesPerLine() * cropped.height())
            img_array = np.array(ptr).reshape(cropped.height(), cropped.width(), 4)
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_BGRA2BGR)

            self.selection_done.emit(img_bgr)
        else:
            self.selection_done.emit(None)

        self.rubber_band.hide()
        self.origin = QPoint()
        self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.selection_done.emit(None)
            self.close()
        super().keyPressEvent(event)
