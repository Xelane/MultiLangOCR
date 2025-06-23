from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QCheckBox, QListWidget, QListWidgetItem,
    QPushButton, QApplication, QMessageBox, QHBoxLayout
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
import json
import os
import pyperclip
from tts import speak_text

class ConfigUI(QWidget):
    def __init__(self, history=None):
        super().__init__()
        self.initial_config = {}
        self.setWindowTitle("MultiLangOCR")
        self.setMinimumSize(500, 400)
        icon_path = "icon.ico"
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
        self.connect_signals()

    def init_ui(self):
        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.handle_item_click)

        self.auto_copy_checkbox = QCheckBox("Copy to Clipboard on capture")
        self.auto_tts_checkbox = QCheckBox("Automatic TTS Playback for every capture")
        self.prefer_ja_checkbox = QCheckBox("Prefer Japanese over Chinese when ambiguous")

        for box in [
            self.auto_copy_checkbox,
            self.auto_tts_checkbox,
            self.prefer_ja_checkbox
        ]:
            box.stateChanged.connect(self.check_unsaved_changes)

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self.save_config)
        self.reset_btn = QPushButton("Restore Defaults")
        self.reset_btn.clicked.connect(self.confirm_restore_defaults)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 12px; color: green;")

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Recent Scans:"))
        layout.addWidget(self.list_widget)
        layout.addWidget(self.auto_copy_checkbox)
        layout.addWidget(self.auto_tts_checkbox)
        layout.addWidget(self.prefer_ja_checkbox)
        layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.reset_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def record_initial_state(self):
        self.initial_config = {
            "auto_copy": self.auto_copy_checkbox.isChecked(),
            "auto_tts": self.auto_tts_checkbox.isChecked(),
            "prefer_ja_over_zh": self.prefer_ja_checkbox.isChecked()
        }

    def show_status(self, message, color="green"):
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.status_timer.start(3000)

    def clear_status(self):
        self.status_label.setText("")

    def load_config(self):
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                data = json.load(f)

            self.auto_copy_checkbox.blockSignals(True)
            self.auto_tts_checkbox.blockSignals(True)
            self.prefer_ja_checkbox.blockSignals(True)

            self.auto_copy_checkbox.setChecked(data.get("auto_copy", True))
            self.auto_tts_checkbox.setChecked(data.get("auto_tts", False))
            self.prefer_ja_checkbox.setChecked(data.get("prefer_ja_over_zh", False))

            self.auto_copy_checkbox.blockSignals(False)
            self.auto_tts_checkbox.blockSignals(False)
            self.prefer_ja_checkbox.blockSignals(False)

    def save_config(self):
        data = {
            "auto_copy": self.auto_copy_checkbox.isChecked(),
            "auto_tts": self.auto_tts_checkbox.isChecked(),
            "prefer_ja_over_zh": self.prefer_ja_checkbox.isChecked()
        }
        with open("config.json", "w") as f:
            json.dump(data, f, indent=4)

        self.record_initial_state()
        self.show_status("Preferences saved.", color="green")

    def check_unsaved_changes(self):
        changed = any([
            self.auto_copy_checkbox.isChecked() != self.initial_config.get("auto_copy"),
            self.auto_tts_checkbox.isChecked() != self.initial_config.get("auto_tts"),
            self.prefer_ja_checkbox.isChecked() != self.initial_config.get("prefer_ja_over_zh")
        ])
        if changed:
            self.show_status("Unsaved changes", color="red")
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
        speak_text(entry["text"], entry["lang"])
        if self.auto_copy_checkbox.isChecked():
            pyperclip.copy(entry["text"])
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
        self.auto_copy_checkbox.setChecked(True)
        self.auto_tts_checkbox.setChecked(False)
        self.prefer_ja_checkbox.setChecked(False)
        self.check_unsaved_changes()
        self.save_config()
        self.show_status("Defaults restored.", color="blue")
    
    def connect_signals(self):
        for box in [
            self.auto_copy_checkbox,
            self.auto_tts_checkbox,
            self.prefer_ja_checkbox
        ]:
            box.stateChanged.connect(self.check_unsaved_changes)


def launch_config_ui(history=[]):
    app = QApplication.instance()
    win = ConfigUI(history=history)
    win.show()
    win.raise_()
    win.activateWindow()
    return win
