#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FrameIO Config Editor (Unified Global + User)
Uppercut VFX Pipeline
Accessible from Main Menu → FrameIO → Edit Config
"""

import flame
import json
import os
import webbrowser
from pathlib import Path
from PySide6 import QtWidgets, QtCore
from lib.frame_io_api import (
    validate_cfg,
    GLOBAL_CONFIG_PATH,
    USER_CONFIG_PATH,
    DEFAULT_CONFIG,
)

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def log(msg):
    print(f"[FrameIO Config Editor] {msg}")

def load_json(path, fallback=None):
    try:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    except Exception as e:
        log(f"WARNING: Error loading {path}: {e}")
    return fallback or {}

def save_json(path, data):
    """Write JSON config safely."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    log(f"Saved {path}")

# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

FRAMEIO_DOCS_URL = "https://developer.frame.io/"

PROJECT_TOKEN_NICKNAME = "nickname"
PROJECT_TOKEN_NAME = "name"

# ---------------------------------------------------------------------
# Main UI
# ---------------------------------------------------------------------

class FrameIOConfigEditor(QtWidgets.QDialog):
    """UI for editing FrameIO global + user settings."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("FrameIO Config Editor — Uppercut Pipeline")
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
        self.resize(640, 520)

        self.layout = QtWidgets.QVBoxLayout(self)

        # Load configs
        default_global = dict(DEFAULT_CONFIG)
        self.global_cfg = load_json(GLOBAL_CONFIG_PATH, default_global)

        self.user_cfg = load_json(
            USER_CONFIG_PATH,
            {
                "frame_io_token": "",
                "frame_io_account_id": "",
                "frame_io_team_id": "",
            },
        )

        self.build_ui()
        self.populate_fields()

    # ------------------------------------------------------
    def build_ui(self):
        tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(tabs)

        #
        # ------------------ GLOBAL TAB ------------------
        #
        global_tab = QtWidgets.QWidget()
        g_layout = QtWidgets.QFormLayout(global_tab)

        # Jobs folder
        self.g_jobs_folder = QtWidgets.QLineEdit()
        jobs_folder_row = QtWidgets.QHBoxLayout()
        jobs_folder_row.addWidget(self.g_jobs_folder)
        btn = QtWidgets.QPushButton("Browse...")
        btn.clicked.connect(self.browse_jobs_folder)
        btn.setFixedWidth(100)
        jobs_folder_row.addWidget(btn)

        # H.264 preset
        self.g_h264 = QtWidgets.QLineEdit()
        h264_row = QtWidgets.QHBoxLayout()
        h264_row.addWidget(self.g_h264)
        btn2 = QtWidgets.QPushButton("Browse...")
        btn2.clicked.connect(self.browse_h264_preset)
        btn2.setFixedWidth(100)
        h264_row.addWidget(btn2)

        # Project token dropdown
        self.g_project_token = QtWidgets.QComboBox()
        self.g_project_token.addItem("Project Nickname", PROJECT_TOKEN_NICKNAME)
        self.g_project_token.addItem("Project Name", PROJECT_TOKEN_NAME)

        # Debug
        self.g_debug = QtWidgets.QCheckBox("Enable verbose FrameIO debug logging")

        # File logging
        self.g_file_logging = QtWidgets.QCheckBox(
            "Enable file logging (logs saved to ~/flame/python/frame_io/logs/)"
        )

        g_layout.addRow("Jobs Folder:", jobs_folder_row)
        g_layout.addRow("H.264 Preset Path:", h264_row)
        g_layout.addRow("Project Token:", self.g_project_token)
        g_layout.addRow("Debug Mode:", self.g_debug)
        g_layout.addRow("File Logging:", self.g_file_logging)

        tabs.addTab(global_tab, "Global Settings")

        #
        # ------------------ USER TAB ------------------
        #
        user_tab = QtWidgets.QWidget()
        u_layout = QtWidgets.QFormLayout(user_tab)

        self.u_token = QtWidgets.QLineEdit()
        self.u_token.setEchoMode(QtWidgets.QLineEdit.Password)  # Mask token

        self.u_account_id = QtWidgets.QLineEdit()
        self.u_team_combo = QtWidgets.QComboBox()

        # Token row: entry + validate + link
        token_row = QtWidgets.QHBoxLayout()
        token_row.addWidget(self.u_token)

        validate_btn = QtWidgets.QPushButton("Validate Token")
        validate_btn.setFixedWidth(120)
        validate_btn.clicked.connect(self.validate_token_clicked)

        docs_btn = QtWidgets.QPushButton("Get Token")
        docs_btn.setFixedWidth(120)
        docs_btn.clicked.connect(lambda: webbrowser.open(FRAMEIO_DOCS_URL))

        token_row.addWidget(validate_btn)
        token_row.addWidget(docs_btn)

        u_layout.addRow("FrameIO Token:", token_row)
        u_layout.addRow("Account ID:", self.u_account_id)
        u_layout.addRow("Team:", self.u_team_combo)

        tabs.addTab(user_tab, "User Settings")

        #
        # ------------------ FOOTER BUTTONS ------------------
        #
        footer_btns = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton("Save All Settings")
        save_btn.clicked.connect(self.save_all)
        reload_btn = QtWidgets.QPushButton("Reload")
        reload_btn.clicked.connect(self.reload)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)

        footer_btns.addStretch()
        footer_btns.addWidget(save_btn)
        footer_btns.addWidget(reload_btn)
        footer_btns.addWidget(close_btn)

        self.layout.addLayout(footer_btns)

        #
        # ------------------ FOOTER PATH INFO ------------------
        #
        footer = QtWidgets.QLabel(
            f"<small><b>Global Config:</b> {GLOBAL_CONFIG_PATH}<br>"
            f"<b>User Config:</b> {USER_CONFIG_PATH}</small>"
        )
        footer.setAlignment(QtCore.Qt.AlignCenter)
        footer.setTextFormat(QtCore.Qt.RichText)
        self.layout.addWidget(footer)

    # ------------------------------------------------------
    def populate_fields(self):
        # Global fields
        self.g_jobs_folder.setText(self.global_cfg.get("jobs_folder", ""))
        self.g_h264.setText(self.global_cfg.get("preset_path_h264", ""))

        token_mode = self.global_cfg.get("project_token", PROJECT_TOKEN_NICKNAME)
        idx = self.g_project_token.findData(token_mode)
        self.g_project_token.setCurrentIndex(idx if idx >= 0 else 0)

        self.g_debug.setChecked(bool(self.global_cfg.get("debug", False)))
        self.g_file_logging.setChecked(bool(self.global_cfg.get("enable_file_logging", False)))

        # User fields
        self.u_token.setText(self.user_cfg.get("frame_io_token", ""))
        self.u_account_id.setText(self.user_cfg.get("frame_io_account_id", ""))

        # Team dropdown
        self.u_team_combo.clear()
        saved_team = self.user_cfg.get("frame_io_team_id", "")
        if saved_team:
            self.u_team_combo.addItem(f"(saved) {saved_team}", saved_team)

    # ------------------------------------------------------
    def browse_jobs_folder(self):
        start = self.g_jobs_folder.text().strip() or "/Volumes"
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Jobs Folder", start)
        if folder:
            self.g_jobs_folder.setText(folder)

    # ------------------------------------------------------
    def browse_h264_preset(self):
        start = self.g_h264.text().strip() or "/opt/Autodesk/presets"
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select H.264 Preset",
            start,
            "XML Files (*.xml);;All Files (*)"
        )
        if file_path:
            self.g_h264.setText(file_path)

    # ------------------------------------------------------
    def validate_token_clicked(self):
        """Validate FrameIO token using validate_cfg()."""
        token = self.u_token.text().strip()
        if not token:
            QtWidgets.QMessageBox.warning(self, "Missing Token", "Please enter your FrameIO token first.")
            return

        # Build temporary config for validation
        test_user_cfg = dict(self.user_cfg)
        test_user_cfg["frame_io_token"] = token

        self.setCursor(QtCore.Qt.WaitCursor)
        ok, msg, merged = validate_cfg(self.global_cfg, test_user_cfg)
        self.setCursor(QtCore.Qt.ArrowCursor)

        if not ok:
            QtWidgets.QMessageBox.critical(self, "FrameIO", msg)
            return

        QtWidgets.QMessageBox.information(self, "FrameIO", msg)

        # Fill account ID
        self.u_account_id.setText(merged.get("frame_io_account_id", ""))

        # Fill team dropdown
        self.u_team_combo.clear()
        for t in merged.get("frame_io_teams", []):
            self.u_team_combo.addItem(f"{t['name']} ({t['id']})", t["id"])

    # ------------------------------------------------------
    def save_all(self):
        """Write global + user config files."""
        # Global
        self.global_cfg.update(
            {
                "jobs_folder": self.g_jobs_folder.text().strip(),
                "preset_path_h264": self.g_h264.text().strip(),
                "project_token": self.g_project_token.currentData(),
                "debug": bool(self.g_debug.isChecked()),
                "enable_file_logging": bool(self.g_file_logging.isChecked()),
            }
        )

        # User
        team_value = self.u_team_combo.currentData()
        if team_value is None:
            team_value = self.user_cfg.get("frame_io_team_id", "")

        self.user_cfg.update(
            {
                "frame_io_token": self.u_token.text().strip(),
                "frame_io_account_id": self.u_account_id.text().strip(),
                "frame_io_team_id": team_value,
            }
        )

        save_json(GLOBAL_CONFIG_PATH, self.global_cfg)
        save_json(USER_CONFIG_PATH, self.user_cfg)

        QtWidgets.QMessageBox.information(self, "Saved", "Settings saved successfully.")

    # ------------------------------------------------------
    def reload(self):
        """Reload JSON files and repopulate UI."""
        self.global_cfg = load_json(GLOBAL_CONFIG_PATH, self.global_cfg)
        self.user_cfg = load_json(USER_CONFIG_PATH, self.user_cfg)
        self.populate_fields()

# ---------------------------------------------------------------------
# Flame Menu Integration
# ---------------------------------------------------------------------

def launch_editor(*args, **kwargs):
    try:
        dlg = FrameIOConfigEditor()
        dlg.exec()
    except Exception as e:
        print(f"[FrameIO Config Editor] ERROR: Failed to launch: {e}")

def get_main_menu_custom_ui_actions():
    return [
        {
            "hierarchy": ["UC FrameIO"],
            "actions": [
                {
                    "name": "Edit Config",
                    "execute": launch_editor,
                    "minimumVersion": "2025",
                }
            ]
        }
    ]
