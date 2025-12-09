#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FrameIO Shot Uploader v1.3.0 — Uppercut VFX Pipeline
Exports h264 .mp4 files to a FROM_FLAME folder and uploads them to FrameIO.
Automatically creates or adds to version stacks using the <shot>_<task> base name.
"""

import os
import flame
import datetime
import re
import traceback
import glob
from PySide6 import QtWidgets
from frameioclient import FrameioClient

from lib.frame_io_api import (
    validate_config,
    get_fio_projects,
    create_fio_project,
    find_fio_asset,
    find_fio_folder,
    create_fio_folder,
    version_asset,
    resolve_stack_root_id,
    log_error,
)
from lib.frame_io_ui import FrameIOProgressDialog

SCRIPT_NAME = "FrameIO Shot Uploader"
VERSION = "v1.3.0"


# ----------------------------------------------------------
# Logging
# ----------------------------------------------------------

def log(msg):
    print(f"[{SCRIPT_NAME}] {msg}")


def show_message(text, title=SCRIPT_NAME):
    """Cross-version safe popup for Flame."""
    try:
        if hasattr(flame, "message_dialog"):
            flame.message_dialog(title, text)
        else:
            QtWidgets.QMessageBox.information(None, title, text)
    except Exception:
        print(f"[{SCRIPT_NAME}] {text}")


# ----------------------------------------------------------
# Base Name Logic (Robust Shot + Task Split)
# ----------------------------------------------------------

def extract_base_name(filename):
    """
    Convert:
        abc_010_comp_jg_v01.mp4
    Into:
        abc_010_comp

    Rule:
      - Shot = first two underscores
      - Task = next segment
      - Everything after <task> is ignored
      - Version block ignored (v01 / V01 / .v01 / -v01)

    Works with:
      uc241217_020_anim_john_v12
      spotA_030_light_mf_v03
      abc_010_comp_jg_v01
    """

    name_no_ext = os.path.splitext(filename)[0]

    # Split into segments
    parts = name_no_ext.split("_")

    if len(parts) < 3:
        # Not enough segments, fall back to removing version tag
        return re.split(r"[._-][vV]\d+", name_no_ext)[0]

    # Shot name = first two segments
    shot = parts[0]
    shot_number = parts[1]

    # Task = third segment
    task = parts[2]

    base = f"{shot}_{shot_number}_{task}"
    return base


# ----------------------------------------------------------
# Export
# ----------------------------------------------------------

def export_mp4(selection, cfg):
    """Export selection to MP4 files."""
    project_nickname = str(flame.projects.current_project.nickname)
    jobs_folder = cfg.get("jobs_folder", "/Volumes/vfx/UC_Jobs")

    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    time = now.strftime("%H%M")

    preset_path = cfg.get("preset_path_h264")
    if not preset_path or not os.path.exists(preset_path):
        show_message("Cannot find Export Preset.", "Error")
        raise RuntimeError(f"Missing preset: {preset_path}")

    export_dir = os.path.join(jobs_folder, project_nickname, "FROM_FLAME", today, time)

    if not os.path.isdir(export_dir):
        try:
            os.makedirs(export_dir, exist_ok=True)
        except Exception:
            show_message(f"Can't make directory: {export_dir}")
            raise

    exporter = flame.PyExporter()
    exporter.foreground = True
    exporter.export_between_marks = False
    exporter.use_top_video_track = True

    for item in selection:
        exporter.export(item, preset_path, export_dir)

    return export_dir


# ----------------------------------------------------------
# Upload to FrameIO
# ----------------------------------------------------------

def upload_to_frameio(export_dir, cfg):
    log("Starting FrameIO upload...")

    project_nickname = str(flame.projects.current_project.nickname)

    # Ensure FrameIO project exists
    try:
        root_asset_id, project_id = get_fio_projects(cfg, project_nickname)
    except Exception:
        root_asset_id, project_id = create_fio_project(cfg, project_nickname)
        create_fio_folder(cfg, root_asset_id, "CONFORMS")
        create_fio_folder(cfg, root_asset_id, "SHOTS")

    token = cfg.get("frame_io_token") or cfg.get("token")
    client = FrameioClient(token)

    # Find or create SHOTS folder
    shots_folder_id = None
    search = find_fio_folder(cfg, project_id, "SHOTS")
    if search != (None, None, None):
        _, shots_folder_id, _ = search
    else:
        shots_folder_id = create_fio_folder(cfg, root_asset_id, "SHOTS")

    # Get list of exported files
    export_path = os.path.join(export_dir, "**", "*")
    files = [f for f in glob.glob(export_path, recursive=True) if os.path.isfile(f)]

    if not files:
        log("No files found to upload.")
        return

    total_files = len(files)
    progress_dialog = FrameIOProgressDialog(total_files, "FrameIO Shot Upload")
    progress_dialog.show()

    had_errors = False
    completed = False

    try:
        for idx, filename in enumerate(files, 1):
            path, file_name = os.path.split(filename)

            progress_dialog.update_total_file(idx, total_files, file_name)
            progress_dialog.update_file_percent(5, f"Preparing upload for {file_name}…")

            log(f"Processing: {file_name}")

            # Extract clean, consistent base name
            base_name = extract_base_name(file_name)
            log(f"Base name for search: {base_name}")

            # Try to find an existing asset with this base name
            search = find_fio_asset(cfg, project_id, base_name)

            if search != (None, None, None):
                asset_type, asset_id, parent_id = search

                # --- Case: Existing file — upload then version it ---
                if asset_type == "file":
                    try:
                        uploaded = client.assets.upload(parent_id, filename)
                        new_asset_id = str(uploaded["id"])

                        try:
                            root_id = resolve_stack_root_id(cfg, asset_id)
                            version_asset(cfg, root_id, new_asset_id)
                            log(f"Versioned {file_name} with asset {asset_id}")
                        except Exception as ve:
                            had_errors = True
                            log(f"WARNING: Versioning failed for {file_name}: {ve}")

                    except Exception as e:
                        had_errors = True
                        log_error(f"Failed to upload {file_name}: {e}", exc_info=True)
                        continue

                # --- Case: Version stack — upload directly into it ---
                elif asset_type == "version_stack":
                    try:
                        client.assets.upload(asset_id, filename)
                    except Exception as e:
                        had_errors = True
                        log_error(f"Failed to upload {file_name}: {e}", exc_info=True)
                        continue

            # --- Case: No match — upload to SHOTS folder ---
            else:
                log(f"No match found. Uploading {file_name} to SHOTS.")
                try:
                    client.assets.upload(shots_folder_id, filename)
                except Exception as e:
                    had_errors = True
                    log_error(f"Upload failed for {file_name}: {e}", exc_info=True)
                    continue

            progress_dialog.update_file_percent(100, f"Uploaded {file_name}")

        completed = True

    finally:
        if completed and not had_errors:
            progress_dialog.finish("FrameIO shot upload complete")
        elif completed:
            progress_dialog.finish("WARNING: Upload complete with warnings")
        else:
            progress_dialog.finish("WARNING: Upload interrupted")


# ----------------------------------------------------------
# Main Entry
# ----------------------------------------------------------

def frame_io_shot_uploader(selection):
    print(f"\n[{SCRIPT_NAME}] {VERSION} — Start")
    try:
        if not selection:
            show_message("Please select one or more clips first.")
            return

        cfg = validate_config()

        export_dir = export_mp4(selection, cfg)
        upload_to_frameio(export_dir, cfg)

        log("Done.")

    except Exception as e:
        log(f"Fatal error: {e}\n{traceback.format_exc()}")
        show_message(f"FrameIO Shot Uploader Error: {e}")


# ----------------------------------------------------------
# Visibility
# ----------------------------------------------------------

def scope_clip(selection):
    return any(isinstance(s, flame.PyClip) for s in selection)


# ----------------------------------------------------------
# Flame Menu
# ----------------------------------------------------------

def get_media_panel_custom_ui_actions():
    return [
        {
            "name": "UC FrameIO",
            "actions": [
                {
                    "name": "Shot Uploader",
                    "order": 1,
                    "isVisible": scope_clip,
                    "execute": frame_io_shot_uploader,
                    "minimumVersion": "2024.2"
                }
            ]
        }
    ]
