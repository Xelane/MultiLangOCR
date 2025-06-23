from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QCheckBox, QListWidget,
    QListWidgetItem, QPushButton, QApplication, QMessageBox, QHBoxLayout 
)
from PyQt6.QtCore import Qt, QTimer
import json
import os
from tts import speak_text
import pyperclip


class ConfigUI(QWidget):
    def __init__(self, history=None):
        super().__init__()
        self.setWindowTitle("MultiLangOCR")
        self.setMinimumSize(500, 400)

        self.history = history if history else []

        layout = QVBoxLayout()

        self.list_widget = QListWidget()
        self.list_widget.itemClicked.connect(self.handle_item_click)

        self.auto_copy_checkbox = QCheckBox("Copy to Clipboard on capture")
        self.auto_tts_checkbox = QCheckBox("Automatic TTS Playback for every capture")
        self.auto_start_checkbox = QCheckBox("Run on system boot")
        self.prefer_ja_checkbox = QCheckBox("Prefer Japanese over Chinese when text is ambiguous")

        self.save_btn = QPushButton("Save Settings")
        self.save_btn.clicked.connect(self.save_config)
        self.reset_btn = QPushButton("Restore Defaults")
        self.reset_btn.clicked.connect(self.confirm_restore_defaults)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 12px; color: green;")
        

        self.status_timer = QTimer()
        self.status_timer.setSingleShot(True)
        self.status_timer.timeout.connect(self.clear_status)

        layout.addWidget(QLabel("Recent Scans:"))
        layout.addWidget(self.list_widget)
        layout.addWidget(self.auto_copy_checkbox)
        layout.addWidget(self.auto_tts_checkbox)
        layout.addWidget(self.auto_start_checkbox)
        layout.addWidget(self.prefer_ja_checkbox)
        layout.addWidget(self.status_label)
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.reset_btn)
        layout.addLayout(btn_layout)

        self.auto_copy_checkbox.stateChanged.connect(self.check_unsaved_changes)
        self.auto_tts_checkbox.stateChanged.connect(self.check_unsaved_changes)
        self.auto_start_checkbox.stateChanged.connect(self.check_unsaved_changes)
        self.prefer_ja_checkbox.stateChanged.connect(self.check_unsaved_changes)

        self.setLayout(layout)
        self.load_config()
        self.initial_config = {
            "auto_copy": self.auto_copy_checkbox.isChecked(),
            "auto_tts": self.auto_tts_checkbox.isChecked(),
            "auto_start": self.auto_start_checkbox.isChecked(),
            "prefer_ja_over_zh": self.prefer_ja_checkbox.isChecked()
        }
        self.load_history()

    def show_status(self, message, color="green"):
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px;")
        self.status_timer.start(3000)  # 3 seconds
    
    def clear_status(self):
        self.status_label.setText("")

    def load_config(self):
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                data = json.load(f)

            # Block signals while loading
            self.auto_copy_checkbox.blockSignals(True)
            self.auto_tts_checkbox.blockSignals(True)
            self.auto_start_checkbox.blockSignals(True)
            self.prefer_ja_checkbox.blockSignals(True)

            self.auto_copy_checkbox.setChecked(data.get("auto_copy", True))
            self.auto_tts_checkbox.setChecked(data.get("auto_tts", False))
            self.auto_start_checkbox.setChecked(data.get("auto_start", False))
            self.prefer_ja_checkbox.setChecked(data.get("prefer_ja_over_zh", False))

            self.auto_copy_checkbox.blockSignals(False)
            self.auto_tts_checkbox.blockSignals(False)
            self.auto_start_checkbox.blockSignals(False)
            self.prefer_ja_checkbox.blockSignals(False)


    def save_config(self):
        data = {
            "auto_copy": self.auto_copy_checkbox.isChecked(),
            "auto_tts": self.auto_tts_checkbox.isChecked(),
            "auto_start": self.auto_start_checkbox.isChecked(),
            "prefer_ja_over_zh": self.prefer_ja_checkbox.isChecked()
        }
        with open("config.json", "w") as f:
            json.dump(data, f, indent=4)
        self.show_status("Preferences saved.", color="green")

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
    
    def check_unsaved_changes(self):
        changed = (
            self.auto_copy_checkbox.isChecked() != self.initial_config.get("auto_copy") or
            self.auto_tts_checkbox.isChecked() != self.initial_config.get("auto_tts") or
            self.auto_start_checkbox.isChecked() != self.initial_config.get("auto_start") or
            self.prefer_ja_checkbox.isChecked() != self.initial_config.get("prefer_ja_over_zh")
        )
        if changed:
            self.show_status("Unsaved changes", color="red")
            self.status_timer.stop()  # Keep the message until saved
        else:
            self.status_label.setText("")


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
        self.auto_start_checkbox.setChecked(False)
        self.prefer_ja_checkbox.setChecked(False)
        self.check_unsaved_changes()
        self.save_config()
        self.initial_config = {
            "auto_copy": self.auto_copy_checkbox.isChecked(),
            "auto_tts": self.auto_tts_checkbox.isChecked(),
            "auto_start": self.auto_start_checkbox.isChecked(),
            "prefer_ja_over_zh": self.prefer_ja_checkbox.isChecked()
        }
        self.show_status("Defaults restored.", color="blue")


def launch_config_ui(history=[]):
    app = QApplication.instance()
    win = ConfigUI(history=history)
    win.show()
    win.raise_()
    win.activateWindow()
    return win
