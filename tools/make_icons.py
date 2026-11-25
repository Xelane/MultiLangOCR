"""Regenerate the app icons from code, so they stay crisp at every size.

    python tools/make_icons.py

Writes:
    icon.ico                    multi-size Windows icon (also used as the tray icon there)
    assets/icon.icns            macOS app icon
    assets/icon_1024.png        master image
    assets/tray_template.png    macOS menu-bar icon (+ @2x), black on transparent
    assets/selftest.png         fixed text image for `--self-test` (drawn here, because
                                a test machine may have no usable fonts)

The .icns step needs macOS (`iconutil`). The generated files are committed,
so building a release never has to run this.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QFontMetricsF, QGuiApplication, QImage,
                         QLinearGradient, QPainter, QPainterPath, QPen)

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

GRADIENT_START = QColor("#4a4695")  # top-left, sampled from the original 32px icon
GRADIENT_END = QColor("#89236c")    # bottom-right
LETTERS = QColor("#f6f0fb")
TEXT = "MLO"


def _new_image(size):
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    return image


def _painter(image):
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    return painter


def app_icon(size, margin_ratio):
    """Purple gradient rounded square with "MLO". macOS icons leave a margin around the square."""
    image = _new_image(size)
    painter = _painter(image)
    margin = size * margin_ratio
    square = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)
    radius = square.width() * 0.225

    gradient = QLinearGradient(square.topLeft(), square.bottomRight())
    gradient.setColorAt(0.0, GRADIENT_START)
    gradient.setColorAt(1.0, GRADIENT_END)
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(square, radius, radius)

    font = QFont("Helvetica Neue")
    font.setBold(True)
    font.setPixelSize(max(8, int(square.width() * 0.40)))
    metrics = QFontMetricsF(font)
    # Fit the text to ~66% of the square's width.
    scale = (square.width() * 0.66) / metrics.horizontalAdvance(TEXT)
    font.setPixelSize(max(8, int(font.pixelSize() * scale)))
    metrics = QFontMetricsF(font)
    path = QPainterPath()
    path.addText(QPointF(0, 0), font, TEXT)
    bounds = path.boundingRect()
    path.translate(square.center().x() - bounds.center().x(), square.center().y() - bounds.center().y())
    painter.setBrush(LETTERS)
    painter.drawPath(path)
    painter.end()
    return image


def tray_template(size):
    """Menu-bar glyph: scan-frame corners around two text lines. Black on transparent."""
    image = _new_image(size)
    painter = _painter(image)
    unit = size / 22.0
    pen = QPen(QColor(0, 0, 0), 1.8 * unit)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)

    lo, hi, arm = 3.0 * unit, 19.0 * unit, 5.0 * unit
    for x, y, dx, dy in ((lo, lo, 1, 1), (hi, lo, -1, 1), (lo, hi, 1, -1), (hi, hi, -1, -1)):
        corner = QPainterPath(QPointF(x + dx * arm, y))
        corner.lineTo(x, y)
        corner.lineTo(x, y + dy * arm)
        painter.drawPath(corner)

    painter.setPen(QPen(QColor(0, 0, 0), 1.7 * unit, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(QPointF(7.5 * unit, 9.2 * unit), QPointF(14.5 * unit, 9.2 * unit))
    painter.drawLine(QPointF(7.5 * unit, 12.8 * unit), QPointF(12.0 * unit, 12.8 * unit))
    painter.end()
    return image


def selftest_image():
    """Two lines of text the self-test must recognise: English, then Japanese."""
    image = QImage(640, 190, QImage.Format.Format_RGB888)
    image.fill(QColor("white"))
    painter = _painter(image)
    painter.setPen(QColor("black"))
    for family, text, baseline in (("Helvetica Neue", "Hello World 2026", 75), ("Hiragino Sans", "こんにちは", 160)):
        font = QFont(family)
        font.setPixelSize(54)
        painter.setFont(font)
        painter.drawText(24, baseline, text)
    painter.end()
    return image


def make_icns(target):
    if sys.platform != "darwin" or not shutil.which("iconutil"):
        print("skipping .icns (needs macOS iconutil)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for base in (16, 32, 128, 256, 512):
            app_icon(base, 0.0977).save(str(iconset / f"icon_{base}x{base}.png"))
            app_icon(base * 2, 0.0977).save(str(iconset / f"icon_{base}x{base}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(target)], check=True)


def make_ico(target):
    with tempfile.TemporaryDirectory() as tmp:
        master = Path(tmp) / "win.png"
        app_icon(256, 0.02).save(str(master))  # Windows icons fill the canvas more than macOS ones
        sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
        Image.open(master).save(target, format="ICO", sizes=sizes)


def main():
    _app = QGuiApplication(sys.argv)  # noqa: F841  (Qt painting needs an application object)
    ASSETS.mkdir(exist_ok=True)
    app_icon(1024, 0.0977).save(str(ASSETS / "icon_1024.png"))
    tray_template(22).save(str(ASSETS / "tray_template.png"))
    tray_template(44).save(str(ASSETS / "tray_template@2x.png"))
    selftest_image().save(str(ASSETS / "selftest.png"))
    make_icns(ASSETS / "icon.icns")
    make_ico(ROOT / "icon.ico")
    print("wrote:", *sorted(str(p.relative_to(ROOT)) for p in [ASSETS / n for n in os.listdir(ASSETS)] + [ROOT / "icon.ico"]))


if __name__ == "__main__":
    main()
