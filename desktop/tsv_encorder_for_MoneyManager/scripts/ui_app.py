# ui_app.py
# -*- coding: utf-8 -*-

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from encoder_core import run_encode


class App(QWidget):
    """MMEnc UI (PySide6)."""

    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle("MMEnc - MoneyManager Encoder")
        self.setMinimumWidth(520)

        self.csv_path: Optional[str] = None
        self.yaml_path: Optional[str] = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # CSV
        self.csv_button = QPushButton("CSVを選択")
        self.csv_button.clicked.connect(self.select_csv)  # type: ignore[arg-type]
        layout.addWidget(self.csv_button)

        self.csv_label = QLabel("未選択")
        self.csv_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.csv_label.setWordWrap(True)
        layout.addWidget(self.csv_label)

        # YAML
        self.yaml_button = QPushButton("YAMLを選択")
        self.yaml_button.clicked.connect(self.select_yaml)  # type: ignore[arg-type]
        layout.addWidget(self.yaml_button)

        self.yaml_label = QLabel("未選択")
        self.yaml_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.yaml_label.setWordWrap(True)
        layout.addWidget(self.yaml_label)

        # Run
        self.run_button = QPushButton("TSV変換")
        self.run_button.clicked.connect(self.run)  # type: ignore[arg-type]
        layout.addWidget(self.run_button)

        layout.addStretch(1)

    def select_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "PayPay CSVを選択",
            str(Path.home()),
            "CSV Files (*.csv);;All Files (*)",
        )
        if path:
            self.csv_path = path
            self.csv_label.setText(path)

    def select_yaml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Preset YAMLを選択",
            str(Path.home()),
            "YAML Files (*.yaml *.yml);;All Files (*)",
        )
        if path:
            self.yaml_path = path
            self.yaml_label.setText(path)

    def run(self) -> None:
        if not self.csv_path or not self.yaml_path:
            QMessageBox.critical(self, "エラー", "CSVとYAMLの両方を選択してください")
            return

        ok, messages = run_encode(self.csv_path, self.yaml_path)
        if ok:
            QMessageBox.information(self, "完了", "\n".join(messages))
        else:
            QMessageBox.critical(self, "エラー", "\n".join(messages))


def run_app() -> None:
    """Run MMEnc UI."""
    app = QApplication.instance() or QApplication(sys.argv)
    win = App()
    win.show()
    app.exec()