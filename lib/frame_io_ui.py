#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Shared UI helpers for FrameIO Flame scripts.
"""

import os
from PySide6 import QtWidgets, QtCore


class FrameIOProgressDialog(QtWidgets.QDialog):
    """Progress dialog shared by uploader scripts."""

    def __init__(self, total_files, title="FrameIO Upload Progress"):
        super().__init__()
        self.setWindowTitle(title)
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.resize(420, 150)

        layout = QtWidgets.QVBoxLayout(self)
        self.status_label = QtWidgets.QLabel("Preparing uploads…")
        self.file_progress = QtWidgets.QProgressBar()
        self.file_progress.setRange(0, 100)
        self.total_progress = QtWidgets.QProgressBar()
        self.total_progress.setRange(0, max(1, total_files))

        layout.addWidget(self.status_label)
        layout.addWidget(QtWidgets.QLabel("Current File"))
        layout.addWidget(self.file_progress)
        layout.addWidget(QtWidgets.QLabel("Overall"))
        layout.addWidget(self.total_progress)

    def update_total_file(self, idx, total, filename):
        self.total_progress.setMaximum(max(1, total))
        self.total_progress.setValue(max(0, idx - 1))
        self.file_progress.setValue(0)
        self.status_label.setText(f"Uploading {os.path.basename(filename)} ({idx}/{total})…")
        QtWidgets.QApplication.processEvents()

    def update_file_percent(self, percent, message=None):
        clamped = max(0, min(100, int(percent)))
        self.file_progress.setValue(clamped)
        if message:
            self.status_label.setText(message)
        QtWidgets.QApplication.processEvents()

    def finish(self, message="Upload complete", delay_ms=1500):
        self.total_progress.setValue(self.total_progress.maximum())
        self.file_progress.setValue(100)
        self.status_label.setText(message)
        QtWidgets.QApplication.processEvents()
        QtCore.QTimer.singleShot(delay_ms, self.accept)

