from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout, QApplication
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QFont, QColor, QPalette

class FlashOverlay(QWidget):
    def __init__(self):
        super().__init__()

        # Window flags and appearance
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(0.9)
        self.setFixedSize(800, 100)

        # Text label setup
        self.label = QLabel("", self)
        self.label.setFont(QFont("Segoe UI", 16))
        self.label.setStyleSheet("color: white; padding: 10px;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        self.setLayout(layout)

        # Background style
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 160))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

        # Hide logic with timer
        self.hide()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def move_to_bottom_center(self):
        app = QApplication.instance()
        if app:
            screen = app.primaryScreen()
            if screen:
                geometry = screen.geometry()
                x = (geometry.width() - self.width()) // 2
                y = geometry.height() - self.height() - 40
                self.move(QPoint(x, y))
        else:
            print("[Overlay] QApplication not initialized.")

    def showEvent(self, event):
        self.move_to_bottom_center()
        super().showEvent(event)

    def display_text(self, text: str):
        self.label.setText(text)
        self.move_to_bottom_center()
        self.show()
        self.raise_()
        self.timer.start(4000)
