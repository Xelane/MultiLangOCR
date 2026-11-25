from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QCheckBox, QListWidget, QListWidgetItem,
    QPushButton, QApplication, QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
import os
import settings
from resources import resource_path
import tts

# Light enough to read on a dark window, still fine on a light one.
STATUS_OK = "#5FDB74"
STATUS_WARN = "#FF7A70"
STATUS_INFO = "#6CB4FF"


# Setting key -> checkbox label, in display order.
CHECKBOXES = {
    "auto_copy": "Copy to Clipboard on capture",
    "auto_tts": "Automatic TTS Playback for every capture",
    "prefer_ja_over_zh": "Prefer Japanese over Chinese when ambiguous",
    "welcome_message": "Speak a welcome message when the app starts",
}


class ConfigUI(QWidget):
    def __init__(self, history=None):
        super().__init__()
        self.initial_config = {}
        self.setWindowTitle("MultiLangOCR")
        self.setMinimumSize(500, 400)
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.history = history or []
        self.status_timer = QTimer(self)
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.clear_status)

        self.init_ui()
        self.load_config()
        self.record_initial_state()
        self.load_history()

    def init_ui(self):
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.handle_item_click)

        self.boxes = {key: QCheckBox(label) for key, label in CHECKBOXES.items()}
        self.auto_copy_checkbox = self.boxes["auto_copy"]
        self.auto_tts_checkbox = self.boxes["auto_tts"]
        self.prefer_ja_checkbox = self.boxes["prefer_ja_over_zh"]
        self.welcome_checkbox = self.boxes["welcome_message"]
        for box in self.boxes.values():
            box.stateChanged.connect(self.check_unsaved_changes)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self.save_config)
        self.reset_btn = QPushButton("Restore Defaults")
        self.reset_btn.clicked.connect(self.confirm_restore_defaults)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"font-size: 12px; color: {STATUS_OK};")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Recent Scans:"))
        layout.addWidget(self.list_widget)
        for box in self.boxes.values():
            layout.addWidget(box)
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.reset_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def record_initial_state(self):
        self.initial_config = {key: box.isChecked() for key, box in self.boxes.items()}

    def show_status(self, message, color=STATUS_OK):
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.status_timer.start(3000)

    def clear_status(self):
        self.status_label.setText("")

    def load_config(self):
        for key, box in self.boxes.items():
            box.blockSignals(True)
            box.setChecked(settings.get(key))
            box.blockSignals(False)

    def save_config(self):
        # update() keeps every other setting (such as the hotkeys) untouched.
        settings.update(**{key: box.isChecked() for key, box in self.boxes.items()})

        self.record_initial_state()
        self.show_status("Preferences saved.", color=STATUS_OK)

    def check_unsaved_changes(self):
        changed = any(box.isChecked() != self.initial_config.get(key) for key, box in self.boxes.items())
        if changed:
            self.show_status("Unsaved changes", color=STATUS_WARN)
            self.status_timer.stop()
        else:
            self.clear_status()

    def load_history(self):
        self.list_widget.clear()
        for item in self.history[:20]:
            text = item.get("text", "")[:60].replace("\n", " ")
            lang = item.get("lang", "")
            list_item = QListWidgetItem(f"[{lang}] {text}")
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.list_widget.addItem(list_item)

    def handle_item_click(self, item):
        entry = item.data(Qt.ItemDataRole.UserRole)
        tts.speak_text(entry["text"], entry["lang"])
        if self.auto_copy_checkbox.isChecked():
            QApplication.clipboard().setText(entry["text"])
            self.show_status("Copied to clipboard.")

    def confirm_restore_defaults(self):
        confirm = QMessageBox.question(
            self, "Restore Defaults",
            "Are you sure you want to restore default settings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.restore_defaults()

    def restore_defaults(self):
        for key, box in self.boxes.items():
            box.setChecked(settings.DEFAULTS[key])
        self.check_unsaved_changes()
        self.save_config()
        self.show_status("Defaults restored.", color=STATUS_INFO)


def launch_config_ui(history=[]):
    app = QApplication.instance()
    win = ConfigUI(history=history)
    win.show()
    win.raise_()
    win.activateWindow()
    return win
