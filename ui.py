# ui.py
from PyQt6.QtWidgets import QLabel, QWidget, QVBoxLayout, QApplication
from PyQt6.QtCore import Qt, QTimer, QPoint
from PyQt6.QtGui import QFont, QColor, QPalette

class FlashOverlay(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowOpacity(0.9)
        self.setFixedSize(800, 100)

        layout = QVBoxLayout()
        self.label = QLabel("", self)
        self.label.setFont(QFont("Segoe UI", 16))
        self.label.setStyleSheet("color: white; padding: 10px;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.setLayout(layout)
        self.hide()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.hide)

        # Set transparent background
        palette = QPalette()
        # FIX: Changed PyQt5 enum access to PyQt6 equivalent for QPalette.ColorRole
        palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 160))
        self.setAutoFillBackground(True)
        self.setPalette(palette)

    def move_to_bottom_center(self):
        if QApplication.instance():
            screen_geometry = QApplication.instance().primaryScreen().geometry()
            x = (screen_geometry.width() - self.width()) // 2
            # Corrected potential typo in y calculation from previous round
            y = screen_geometry.height() - self.height() - 40
            self.move(QPoint(x, y))
        else:
            print("Warning: QApplication not initialized when attempting to position FlashOverlay.")

    def showEvent(self, event):
        self.move_to_bottom_center()
        super().showEvent(event)

    def display_text(self, text):
        self.label.setText(text)
        self.move_to_bottom_center()
        self.show()
        self.raise_()
        self.timer.start(4000)