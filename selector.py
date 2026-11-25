"""Screen-region selection.

RegionSelector.start() grabs every screen, shows one full-screen overlay per
screen, and emits selection_done(img_bgr) with the cropped region as a BGR
numpy array (or None if the user cancelled / capture was impossible).

Coordinates: widget coordinates are logical (device-independent) pixels, while
the screen grab is in physical pixels (2x on Retina, 1.25x/1.5x on scaled
Windows displays). The crop rectangle is scaled by image width / screen
width, so it is right for any scale factor, including fractional ones.
"""
import os
import sys

import numpy as np
from PyQt6.QtCore import QObject, QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QCursor, QGuiApplication, QImage, QPainter, QPen
from PyQt6.QtWidgets import QWidget

from permissions import ensure_screen_capture_permission

IS_MAC = sys.platform == "darwin"

DEBUG = bool(os.environ.get("MULTILANGOCR_DEBUG"))
DEBUG_DIR = "debug_ocr"

MIN_SELECTION = 4  # logical px; smaller drags are treated as a stray click
DIM_COLOR = QColor(0, 0, 0, 90)
BORDER_COLOR = QColor(0, 160, 255)


def qimage_to_bgr(image):
    """Copy a QImage into a contiguous (h, w, 3) uint8 BGR array."""
    image = image.convertToFormat(QImage.Format.Format_BGR888)
    w, h, stride = image.width(), image.height(), image.bytesPerLine()
    ptr = image.constBits()
    ptr.setsize(stride * h)
    rows = np.frombuffer(ptr, dtype=np.uint8).reshape(h, stride)
    # Rows are padded to 4 bytes; slice the padding off, and copy so the
    # array doesn't point into memory owned by the QImage.
    return np.ascontiguousarray(rows[:, : w * 3].reshape(h, w, 3))


class _ScreenOverlay(QWidget):
    """Frozen screenshot of one screen with a drag-to-select rectangle."""

    finished = pyqtSignal(object)  # QImage of the selection, or None

    def __init__(self, screen, pixmap):
        super().__init__()
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
        if not IS_MAC:
            # Hides it from the Windows taskbar. On macOS a Qt.Tool window
            # vanishes whenever the app isn't frontmost, which is always true
            # for a tray app, so it is not used there.
            flags |= Qt.WindowType.Tool
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._screen = screen
        self._pixmap = pixmap
        self._image = pixmap.toImage()
        self._start = None
        self._current = None

        self.setScreen(screen)
        self.setGeometry(screen.geometry())

    def screen_contains_cursor(self):
        return self._screen.geometry().contains(QCursor.pos())

    def _offset(self):
        """Where the screen's top-left corner sits in widget coordinates.

        Normally (0, 0). If the OS shifts the window (e.g. below the macOS
        menu bar) this keeps drawing and cropping aligned with the screenshot.
        """
        return self._screen.geometry().topLeft() - self.mapToGlobal(QPoint(0, 0))

    def _selection_rect(self):
        if self._start is None or self._current is None:
            return None
        return QRect(self._start, self._current).normalized()

    def _crop(self, rect):
        """Crop `rect` (widget coords) out of the screenshot; None if empty."""
        geo = self._screen.geometry()
        scale_x = self._image.width() / geo.width()
        scale_y = self._image.height() / geo.height()
        top_left = rect.topLeft() - self._offset()
        src = QRect(
            round(top_left.x() * scale_x),
            round(top_left.y() * scale_y),
            round(rect.width() * scale_x),
            round(rect.height() * scale_y),
        ).intersected(self._image.rect())
        if src.isEmpty():
            return None
        cropped = self._image.copy(src)
        if DEBUG:
            self._dump_debug(rect, src, cropped, scale_x, scale_y)
        return cropped

    def _dump_debug(self, rect, src, cropped, scale_x, scale_y):
        """MULTILANGOCR_DEBUG=1: save what was captured to debug_ocr/."""
        os.makedirs(DEBUG_DIR, exist_ok=True)
        shot = self._image.copy()
        shot.setDevicePixelRatio(1)  # so the painter below works in raw pixels
        painter = QPainter(shot)
        painter.setPen(QPen(QColor(255, 0, 0), 4))
        painter.drawRect(src)
        painter.end()
        shot.save(f"{DEBUG_DIR}/screen_with_selection.png")
        cropped.save(f"{DEBUG_DIR}/selection.png")
        print(
            f"[Selector] widget rect={rect.getRect()} window={self.geometry().getRect()} "
            f"screen={self._screen.geometry().getRect()} offset=({self._offset().x()},{self._offset().y()}) "
            f"image={self._image.width()}x{self._image.height()} scale=({scale_x:.2f},{scale_y:.2f}) "
            f"crop={src.getRect()}"
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        target = QRect(self._offset(), self._screen.geometry().size())
        painter.drawPixmap(target, self._pixmap)
        painter.fillRect(self.rect(), DIM_COLOR)

        rect = self._selection_rect()
        if rect is not None:
            painter.save()
            painter.setClipRect(rect)
            painter.drawPixmap(target, self._pixmap)  # selection shown undimmed
            painter.restore()
            painter.setPen(QPen(BORDER_COLOR, 2))
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.finished.emit(None)
        elif event.button() == Qt.MouseButton.LeftButton:
            self._start = self._current = event.position().toPoint()
            self.update()

    def mouseMoveEvent(self, event):
        if self._start is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or self._start is None:
            return
        rect = self._selection_rect()
        self._start = self._current = None
        if rect.width() < MIN_SELECTION or rect.height() < MIN_SELECTION:
            self.finished.emit(None)
        else:
            self.finished.emit(self._crop(rect))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.finished.emit(None)
        else:
            super().keyPressEvent(event)


class RegionSelector(QObject):
    selection_done = pyqtSignal(object)  # BGR ndarray, or None if cancelled

    def __init__(self):
        super().__init__()
        self._overlays = []

    @property
    def is_active(self):
        return bool(self._overlays)

    def start(self):
        if self._overlays:
            return
        if not ensure_screen_capture_permission():
            self.selection_done.emit(None)
            return

        # Grab every screen BEFORE showing any overlay, or the overlays
        # would end up in the screenshots.
        grabs = []
        for screen in QGuiApplication.screens():
            pixmap = screen.grabWindow(0)
            if not pixmap.isNull():
                grabs.append((screen, pixmap))
        if not grabs:
            print("[Selector] Could not capture any screen.")
            self.selection_done.emit(None)
            return

        for screen, pixmap in grabs:
            overlay = _ScreenOverlay(screen, pixmap)
            overlay.finished.connect(self._on_finished)
            self._overlays.append(overlay)
            overlay.show()

        # Keyboard focus (Esc to cancel) goes to the overlay under the cursor.
        active = next((o for o in self._overlays if o.screen_contains_cursor()), self._overlays[0])
        active.raise_()
        active.activateWindow()
        active.setFocus()

    def _on_finished(self, image):
        overlays, self._overlays = self._overlays, []
        if not overlays:
            return  # already finished (e.g. two overlays reporting at once)
        for overlay in overlays:
            overlay.close()
            overlay.deleteLater()
        self.selection_done.emit(qimage_to_bgr(image) if image is not None else None)
