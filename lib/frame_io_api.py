#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FrameIO API Helpers — Uppercut VFX Pipeline
Centralized config, API functions, and utilities
"""

import os
import json
import xml.etree.ElementTree as ET
import requests
import logging
import traceback
from datetime import datetime
from pathlib import Path

# FrameIO client import - may not be available in all environments
try:
    from frameioclient import FrameioClient
except ImportError:
    FrameioClient = None

# ---------------------------------------------------------------------
# Config locations
# ---------------------------------------------------------------------

SCRIPT_PATH = "/opt/Autodesk/shared/python/frame_io"
GLOBAL_CONFIG_PATH = os.path.join(SCRIPT_PATH, "config", "shared_config.json")
USER_CONFIG_PATH = os.path.expanduser("~/flame/python/frame_io/user_config.json")
LEGACY_XML_CONFIG_PATH = os.path.join(SCRIPT_PATH, "config", "config.xml")
LEGACY_USER_XML_CONFIG_PATH = os.path.expanduser("~/flame/python/frame_io/config.xml")
LOG_DIR = os.path.expanduser("~/flame/python/frame_io/logs")

DEFAULT_CONFIG = {
    "frame_io_token": "",
    "frame_io_account_id": "",
    "frame_io_team_id": "",
    "jobs_folder": "/Volumes/vfx/UC_Jobs",
    "preset_path_h264": "/opt/Autodesk/shared/python/frame_io/presets/UC H264 10Mbits.xml",
    "project_token": "nickname",
    "debug": False,
    "enable_file_logging": False,
}

STATUS_TO_FLAME = {
    "approved": {
        "label": "Approved",
        "colour": (0.11372549086809158, 0.26274511218070984, 0.1764705926179886),
    },
    "needs_review": {
        "label": "Needs Review",
        "colour": (0.6000000238418579, 0.3450980484485626, 0.16470588743686676),
    },
    "in_progress": {
        "label": "In Progress",
        "colour": (0.26274511218070984, 0.40784314274787903, 0.5019607543945312),
    },
}

FLAME_LABEL_TO_STATUS = {info["label"]: status for status, info in STATUS_TO_FLAME.items()}

# ---------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------

_logger = None
_file_handler = None

def _setup_logging(cfg):
    """Setup file logging if enabled in config."""
    global _logger, _file_handler
    
    if not cfg.get("enable_file_logging", False):
        if _file_handler and _logger:
            _logger.removeHandler(_file_handler)
            _file_handler = None
        return
    
    if _logger is None:
        _logger = logging.getLogger("frame_io")
        _logger.setLevel(logging.DEBUG)
    
    if _file_handler is None:
        # Create log directory if it doesn't exist
        os.makedirs(LOG_DIR, exist_ok=True)
        
        # Create log file with timestamp
        log_file = os.path.join(LOG_DIR, f"frame_io_{datetime.now().strftime('%Y%m%d')}.log")
        _file_handler = logging.FileHandler(log_file)
        _file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        _file_handler.setFormatter(formatter)
        _logger.addHandler(_file_handler)

def debug_print(cfg, msg):
    """Print debug message if debug mode is enabled."""
    if cfg.get("debug", False):
        print(f"[frame_io_api DEBUG] {msg}")
    if _logger:
        _logger.debug(msg)

def log(msg, level="info"):
    """Log message to console and optionally to file."""
    print(f"[frame_io_api] {msg}")
    if _logger:
        if level == "error":
            _logger.error(msg)
        elif level == "warning":
            _logger.warning(msg)
        elif level == "debug":
            _logger.debug(msg)
        else:
            _logger.info(msg)

def log_error(msg, exc_info=None):
    """Log error with optional exception info."""
    print(f"[frame_io_api ERROR] {msg}")
    if _logger:
        _logger.error(msg, exc_info=exc_info)

# ---------------------------------------------------------------------
# Load + Merge Configs
# ---------------------------------------------------------------------

def _load_json(path):
    """Load config from JSON file."""
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"[frame_io_api] WARNING: Failed to load {path}: {e}")
    return {}

def _load_xml_config(path):
    """Load config from XML file (legacy support)."""
    try:
        if os.path.exists(path):
            tree = ET.parse(path)
            root = tree.getroot()
            cfg = {}
            for setting in root.iter("frame_io_settings"):
                cfg["frame_io_token"] = setting.find("token").text or ""
                cfg["frame_io_account_id"] = setting.find("account_id").text or ""
                cfg["frame_io_team_id"] = setting.find("team_id").text or ""
                cfg["jobs_folder"] = setting.find("jobs_folder").text or DEFAULT_CONFIG["jobs_folder"]
                cfg["preset_path_h264"] = setting.find("preset_path_h264").text or DEFAULT_CONFIG["preset_path_h264"]
            return cfg
    except Exception as e:
        print(f"[frame_io_api] WARNING: Failed to load XML {path}: {e}")
    return {}

def _migrate_xml_to_json(xml_path, json_path):
    """Migrate XML config to JSON format."""
    try:
        xml_cfg = _load_xml_config(xml_path)
        if xml_cfg:
            # Ensure directory exists
            os.makedirs(os.path.dirname(json_path), exist_ok=True)
            # Write JSON config
            with open(json_path, "w") as f:
                json.dump(xml_cfg, f, indent=2)
            log(f"Migrated XML config to JSON: {json_path}")
            return True
    except Exception as e:
        log(f"WARNING: Failed to migrate XML to JSON: {e}")
    return False

def validate_config():
    """Merge global, user, and legacy configs, ensuring FrameIO token exists."""
    cfg = DEFAULT_CONFIG.copy()

    # 1. Try to load JSON configs first
    for path in [GLOBAL_CONFIG_PATH, USER_CONFIG_PATH]:
        if os.path.exists(path):
            cfg.update(_load_json(path))

    # 2. If JSON doesn't exist but XML does, migrate it
    if not os.path.exists(GLOBAL_CONFIG_PATH) and os.path.exists(LEGACY_XML_CONFIG_PATH):
        _migrate_xml_to_json(LEGACY_XML_CONFIG_PATH, GLOBAL_CONFIG_PATH)
        if os.path.exists(GLOBAL_CONFIG_PATH):
            cfg.update(_load_json(GLOBAL_CONFIG_PATH))

    if not os.path.exists(USER_CONFIG_PATH) and os.path.exists(LEGACY_USER_XML_CONFIG_PATH):
        _migrate_xml_to_json(LEGACY_USER_XML_CONFIG_PATH, USER_CONFIG_PATH)
        if os.path.exists(USER_CONFIG_PATH):
            cfg.update(_load_json(USER_CONFIG_PATH))

    # 3. Fallback to legacy XML if JSON still doesn't exist
    if not os.path.exists(GLOBAL_CONFIG_PATH) and os.path.exists(LEGACY_XML_CONFIG_PATH):
        cfg.update(_load_xml_config(LEGACY_XML_CONFIG_PATH))

    if not os.path.exists(USER_CONFIG_PATH) and os.path.exists(LEGACY_USER_XML_CONFIG_PATH):
        cfg.update(_load_xml_config(LEGACY_USER_XML_CONFIG_PATH))

    # 4. Normalize field names (support both old and new naming)
    if "token" in cfg and not cfg.get("frame_io_token"):
        cfg["frame_io_token"] = cfg.pop("token")
    if "account_id" in cfg and not cfg.get("frame_io_account_id"):
        cfg["frame_io_account_id"] = cfg.pop("account_id")
    if "team_id" in cfg and not cfg.get("frame_io_team_id"):
        cfg["frame_io_team_id"] = cfg.pop("team_id")

    # 5. Validate required fields (check both old and new field names)
    token = cfg.get("frame_io_token") or cfg.get("token")
    account_id = cfg.get("frame_io_account_id") or cfg.get("account_id")
    team_id = cfg.get("frame_io_team_id") or cfg.get("team_id")

    # 6. Setup logging if enabled
    _setup_logging(cfg)

    # 7. Validate with user-friendly error messages
    errors = []
    if not token:
        errors.append("FrameIO token is missing. Please configure it in the Config Editor (Main Menu → UC FrameIO → Edit Config).")
    if not account_id:
        errors.append("FrameIO account ID is missing. Please configure it in the Config Editor.")
    if not team_id:
        errors.append("FrameIO team ID is missing. Please configure it in the Config Editor.")
    
    if errors:
        error_msg = "\n".join(f"  • {e}" for e in errors)
        raise RuntimeError(f"Configuration Error:\n{error_msg}")

    # 8. Normalize to new field names for consistent access
    cfg["frame_io_token"] = token
    cfg["frame_io_account_id"] = account_id
    cfg["frame_io_team_id"] = team_id
    cfg["project_token"] = cfg.get("project_token", "nickname")
    cfg["debug"] = bool(cfg.get("debug", False))
    cfg["enable_file_logging"] = bool(cfg.get("enable_file_logging", False))

    return cfg

# ---------------------------------------------------------------------
# validate_cfg – UI-friendly, full API validation
# Returns: (ok: bool, message: str, merged_cfg: dict)
# ---------------------------------------------------------------------
def validate_cfg(global_cfg: dict, user_cfg: dict):
    """
    Validate FrameIO config AND token via live API calls.
    This is for the Config Editor UI (not for runtime scripts).
    
    Returns:
        (ok, message, merged_cfg)
    """

    merged = {}

    # ---- 1. Merge configs (UI supplies these dicts) ------------------
    merged.update(global_cfg or {})
    merged.update(user_cfg or {})

    # Normalize field names
    token = merged.get("frame_io_token") or merged.get("token")
    account_id = merged.get("frame_io_account_id") or merged.get("account_id")
    team_id = merged.get("frame_io_team_id") or merged.get("team_id")

    merged["frame_io_token"] = token or ""
    merged["frame_io_account_id"] = account_id or ""
    merged["frame_io_team_id"] = team_id or ""

    # ---- 2. Validate token field presence ----------------------------
    if not token:
        return False, "Missing FrameIO API token.", merged

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    # ---- 3. Validate token by calling /me ----------------------------
    try:
        r = requests.get("https://api.frame.io/v2/me", headers=headers, timeout=10)
    except Exception as e:
        return False, f"Network error: {e}", merged

    if r.status_code == 401:
        return False, "Invalid FrameIO token (401 Unauthorized).", merged

    if r.status_code != 200:
        return False, f"Unexpected API response: {r.status_code} {r.text[:160]}", merged

    try:
        me = r.json()
    except Exception:
        return False, "Invalid JSON from FrameIO API (/me).", merged

    # Extract account_id if available
    merged["frame_io_account_id"] = me.get("account_id", "")

    # ---- 4. Fetch teams ------------------------------------------------
    try:
        r_teams = requests.get("https://api.frame.io/v2/teams", headers=headers, timeout=10)
        if r_teams.status_code == 200:
            teams_data = r_teams.json()
        else:
            teams_data = []
    except Exception:
        teams_data = []

    # Format teams list for UI
    teams_list = []
    for t in teams_data:
        if "id" in t:
            teams_list.append({
                "id": t["id"],
                "name": t.get("name", "Unnamed Team")
            })

    merged["frame_io_teams"] = teams_list

    # ---- 5. Auto-select team if not already chosen -------------------
    if not merged.get("frame_io_team_id") and teams_list:
        merged["frame_io_team_id"] = teams_list[0]["id"]

    return True, "FrameIO token validated successfully.", merged


# ---------------------------------------------------------------------
# FrameIO Client Helpers
# ---------------------------------------------------------------------

def get_client(cfg):
    """Get FrameIO client instance."""
    if FrameioClient is None:
        raise RuntimeError("frameioclient module not installed. Please install it using: pip install frameioclient")
    token = cfg.get("frame_io_token") or cfg.get("token")
    if not token:
        raise RuntimeError("FrameIO token missing in config.")
    return FrameioClient(token)

def get_headers(cfg):
    """Get standard FrameIO API headers."""
    token = cfg.get("frame_io_token") or cfg.get("token")
    if not token:
        raise RuntimeError("FrameIO token missing in config.")
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

# ---------------------------------------------------------------------
# Error Handling & Retry Logic
# ---------------------------------------------------------------------

def _retry_request(func, max_retries=3, delay=1, *args, **kwargs):
    """Retry a request function with exponential backoff."""
    import time
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            if attempt < max_retries - 1:
                wait_time = delay * (2 ** attempt)
                log(f"Request failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...", "warning")
                time.sleep(wait_time)
            else:
                log_error(f"Request failed after {max_retries} attempts: {e}", exc_info=True)
                raise RuntimeError(f"Network error: Unable to connect to FrameIO API after {max_retries} attempts. Please check your internet connection.")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait_time = delay * (2 ** attempt)
                log(f"Server error {e.response.status_code} (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...", "warning")
                time.sleep(wait_time)
            else:
                log_error(f"HTTP error: {e}", exc_info=True)
                raise
        except Exception as e:
            log_error(f"Unexpected error: {e}", exc_info=True)
            raise

# ---------------------------------------------------------------------
# Project Helpers
# ---------------------------------------------------------------------

def get_fio_projects(cfg, project_name):
    """Get FrameIO Project ID using the Flame Project Name."""
    headers = get_headers(cfg)
    team_id = cfg.get("frame_io_team_id") or cfg.get("team_id")
    
    url = f"https://api.frame.io/v2/teams/{team_id}/projects"
    query = {
        "filter[archived]": "none",
        "include_deleted": "false"
    }
    
    def _make_request():
        response = requests.get(url, headers=headers, params=query, timeout=15)
        response.raise_for_status()
        return response.json()
    
    try:
        data = _retry_request(_make_request)
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Failed to fetch FrameIO projects: {e}")

    # print("\n=== FRAME.IO PROJECT LIST ===")
    # for p in data:
    #     print("•", p.get("name"))
    # print("=== END LIST ===\n")

    for project in data:
        if project.get("_type") == "project" and project.get("name") == project_name:
            root_asset_id = project.get("root_asset_id")
            project_id = project.get("id")
            log(f"Found FrameIO project '{project_name}': {project_id}")
            return (root_asset_id, project_id)
    
    raise RuntimeError(f"FrameIO project '{project_name}' not found. Please ensure the project name matches exactly in FrameIO.")

def create_fio_project(cfg, project_name):
    """Create a new FrameIO project."""
    headers = get_headers(cfg)
    team_id = cfg.get("frame_io_team_id") or cfg.get("team_id")
    
    url = f"https://api.frame.io/v2/teams/{team_id}/projects"
    payload = {
        "name": project_name,
        "private": False
    }
    
    log(f"Creating FrameIO project '{project_name}'...")
    
    def _make_request():
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    
    try:
        data = _retry_request(_make_request)
    except RuntimeError:
        raise
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            raise RuntimeError(f"Permission denied: Your FrameIO token doesn't have permission to create projects in team {team_id}.")
        raise RuntimeError(f"Failed to create FrameIO project: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to create FrameIO project '{project_name}': {e}")
    
    root_asset_id = data.get("root_asset_id")
    project_id = data.get("id")
    log(f"Created FrameIO project '{project_name}': {project_id}")
    
    return (root_asset_id, project_id)

# ---------------------------------------------------------------------
# Asset Search
# ---------------------------------------------------------------------


def find_fio_asset(cfg, project_id, base_name, asset_type="file"):
    """Search for a FrameIO asset by name.

    Uses a preference order:
    1) Exact name match
    2) Case-insensitive exact match
    3) Partial (base_name contained in asset name)

    Returns (asset_type, asset_id, parent_id) or (None, None, None) on failure.
    """
    headers = get_headers(cfg)
    account_id = cfg.get("frame_io_account_id") or cfg.get("account_id")
    team_id = cfg.get("frame_io_team_id") or cfg.get("team_id")

    url = "https://api.frame.io/v2/search/assets"
    query = {
        "account_id": account_id,
        "project_id": project_id,
        "q": base_name,
        "team_id": team_id,
        "type": asset_type,
    }

    def _make_request():
        response = requests.get(url, headers=headers, params=query, timeout=15)
        response.raise_for_status()
        return response.json()

    try:
        data = _retry_request(_make_request)
    except RuntimeError:
        # _retry_request already logged; bubble up if caller wants to handle
        raise
    except Exception as e:
        log_error(
            f"Failed to search for FrameIO asset '{base_name}': {e}",
            exc_info=True,
        )
        return (None, None, None)

    if not data:
        return (None, None, None)

    exact_match = None
    ci_match = None
    partial_match = None
    base_lower = base_name.lower()

    for item in data:
        # Respect requested type if provided
        if asset_type and item.get("type") != asset_type:
            continue

        name = (item.get("name") or "").strip()
        name_lower = name.lower()

        if name == base_name:
            exact_match = item
            break
        if name_lower == base_lower and ci_match is None:
            ci_match = item
        if base_lower in name_lower and partial_match is None:
            partial_match = item

    item = exact_match or ci_match or partial_match
    if not item:
        return (None, None, None)

    asset_type = item.get("type")
    asset_id = item.get("id")
    parent_id = item.get("parent_id")

    log(f"FrameIO search for '{base_name}' returned asset ID: {asset_id}")

    return (asset_type, asset_id, parent_id)


def find_fio_folder(cfg, project_id, folder_name):
    """Search for a FrameIO folder by name."""
    return find_fio_asset(cfg, project_id, folder_name, asset_type="folder")

# ---------------------------------------------------------------------
# Folder Management
# ---------------------------------------------------------------------

def create_fio_folder(cfg, root_asset_id, folder_name):
    """Create a FrameIO folder."""
    headers = get_headers(cfg)
    
    url = f"https://api.frame.io/v2/assets/{root_asset_id}/children"
    payload = {
        "name": folder_name,
        "type": "folder"
    }
    
    log(f"Creating FrameIO folder '{folder_name}'...")
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    folder_id = data.get("id")
    log(f"Created FrameIO folder '{folder_name}': {folder_id}")
    return folder_id

# ---------------------------------------------------------------------
# Asset Management
# ---------------------------------------------------------------------


def resolve_stack_root_id(cfg, asset_id):
    """Given any asset ID, return the root version-stack asset ID if available.

    This avoids 422 errors when attempting to version against a child asset
    instead of the version stack root.
    """
    headers = get_headers(cfg)
    url = f"https://api.frame.io/v2/assets/{asset_id}"

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        log_error(f"Failed to resolve stack root for asset {asset_id}: {e}", exc_info=True)
        # Fallback: return original asset_id so behavior is unchanged
        return asset_id

    # Case 1: This asset is itself a version stack root
    if data.get("type") == "version_stack" and not data.get("is_versioned", False):
        return asset_id

    # Case 2: Version stack data is present
    vs = data.get("version_stack") or {}
    root_id = vs.get("id")
    if root_id:
        return root_id

    # Case 3: Older APIs may expose original_asset_id
    root_id = data.get("original_asset_id")
    if root_id:
        return root_id

    # Fallback: no stack info, return original
    return asset_id


def version_asset(cfg, asset_id, next_asset_id):
    """Create a version stack by linking two assets.

    asset_id: existing 'base' asset in FrameIO
    next_asset_id: newly uploaded asset to be added as the next version
    """
    headers = get_headers(cfg)
    url = f"https://api.frame.io/v2/assets/{asset_id}/version"
    payload = {"next_asset_id": next_asset_id}

    try:
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=15,
        )

        if response.status_code == 422:
            # Keep behavior (raise), but add a more descriptive log first.
            log(
                "WARNING: FrameIO returned 422 Unprocessable Entity when creating "
                "a version stack. This usually means the base asset is itself "
                "already a version, or is not a stackable video asset "
                f"(asset_id={asset_id}, next_asset_id={next_asset_id})."
            )

        response.raise_for_status()
        log(f"Created version stack: {asset_id} -> {next_asset_id}")

    except Exception as e:
        log_error(
            f"Failed to create version stack for "
            f"asset_id={asset_id} next_asset_id={next_asset_id}: {e}",
            exc_info=True,
        )
        raise

# ---------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------

def get_asset_comments(cfg, asset_id, include_replies=True):
    """Fetch comments for a given asset."""
    headers = get_headers(cfg)
    
    url = f"https://api.frame.io/v2/assets/{asset_id}/comments"
    query = {
        "include": "replies,user" if include_replies else "user",
        "page_size": 500
    }
    
    response = requests.get(url, headers=headers, params=query, timeout=20)
    response.raise_for_status()
    data = response.json()
    
    log(f"Retrieved {len(data)} comment(s) for asset {asset_id}")
    return data

# ---------------------------------------------------------------------
# Status Management
# ---------------------------------------------------------------------

def get_asset_status(cfg, asset_id):
    """Get the status/label of an asset."""
    headers = get_headers(cfg)
    
    url = f"https://api.frame.io/v2/assets/{asset_id}"
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
    
    return data.get("label")

def set_asset_status(cfg, asset_id, status):
    """Set the status/label of an asset."""
    headers = get_headers(cfg)
    
    url = f"https://api.frame.io/v2/assets/{asset_id}"
    payload = {
        "label": status
    }
    
    response = requests.put(url, json=payload, headers=headers, timeout=15)
    response.raise_for_status()
    log(f"Set asset {asset_id} status to '{status}'")


def map_status_to_flame(status):
    """Return flame label/colour mapping for a FrameIO status."""
    return STATUS_TO_FLAME.get(status)


def map_flame_label_to_status(label):
    """Return FrameIO status string for a Flame colour label."""
    return FLAME_LABEL_TO_STATUS.get(label)

# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def seconds_to_tc(seconds, fps=24):
    """Convert seconds to timecode string (HH:MM:SS:FF)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    frames = int(round((seconds % 1) * fps))
    return f"{hours:02}:{minutes:02}:{secs:02}:{frames:02}"

def timecode_to_frames(tc, fps):
    """Convert HH:MM:SS:FF to frame number."""
    try:
        h, m, s, f = [int(x) for x in tc.split(":")]
        return int(round(((h * 3600) + (m * 60) + s) * fps + f))
    except Exception:
        return 0

def extract_fps_from_rate(rate):
    """Sanitize frame rate string like '23.98 fps' -> 23.98 (float)."""
    import re
    if isinstance(rate, (float, int)):
        return float(rate)
    regex = r'\s[a-zA-Z]*'
    test_str = str(rate)
    subst = ""
    fixed_framerate = float(re.sub(regex, subst, test_str, 0))
    return round(fixed_framerate, 3)

