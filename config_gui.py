from PyQt6.QtWidgets import QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QComboBox, QMessageBox
import json
import os

class ConfigWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OCR App Settings")

        self.ocr_hotkey_input = QLineEdit()
        self.tts_hotkey_input = QLineEdit()
        self.default_lang_dropdown = QComboBox()
        self.default_lang_dropdown.addItems(['en', 'ja', 'zh-cn', 'zh-tw'])

        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_config)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("OCR Hotkey:"))
        layout.addWidget(self.ocr_hotkey_input)
        layout.addWidget(QLabel("TTS Hotkey:"))
        layout.addWidget(self.tts_hotkey_input)
        layout.addWidget(QLabel("Default OCR Language:"))
        layout.addWidget(self.default_lang_dropdown)
        layout.addWidget(self.save_btn)

        self.setLayout(layout)
        self.load_config()

    def load_config(self):
        if os.path.exists("config.json"):
            with open("config.json", "r") as f:
                data = json.load(f)
                self.ocr_hotkey_input.setText(data.get("ocr_hotkey", "alt+q"))
                self.tts_hotkey_input.setText(data.get("tts_hotkey", "alt+w"))
                self.default_lang_dropdown.setCurrentText(data.get("default_lang", "en"))

    def save_config(self):
        data = {
            "ocr_hotkey": self.ocr_hotkey_input.text(),
            "tts_hotkey": self.tts_hotkey_input.text(),
            "default_lang": self.default_lang_dropdown.currentText()
        }
        with open("config.json", "w") as f:
            json.dump(data, f, indent=4)
        QMessageBox.information(self, "Saved", "Configuration saved successfully.")
        self.close()
