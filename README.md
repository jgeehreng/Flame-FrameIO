# Flame-FrameIO Scripts

This repository contains a collection of Python scripts for integrating Autodesk Flame with Frame.io. These scripts facilitate operations such as uploading media, retrieving comments, and synchronizing asset statuses between Flame and Frame.io.

## Features

*   **Shot Uploader**: Exports H.264 MP4s from Flame to a local job folder and uploads them to a "SHOTS" folder in the corresponding Frame.io project. Supports version stacking.
*   **Conform Uploader**: Similar to the Shot Uploader, but targets a "CONFORMS" folder in Frame.io. Includes automatic version upping if a previously uploaded version is detected.
*   **Get Comments**: Fetches comments from Frame.io assets and creates corresponding markers on Flame clips or segments.
*   **Get Status**: Retrieves asset statuses (labels) from Frame.io and applies corresponding color labels to items in Flame.
*   **Set Status**: Updates Frame.io asset statuses (labels) based on the color labels of selected items in Flame.

## Core Technology

*   **Frame.io API**: These scripts utilize the official Frame.io V2 API.
*   **Python SDK**: Interactions with the Frame.io API are primarily handled by the official `frameioclient` Python SDK.
*   **Flame Python API**: Scripts integrate with Flame using its Python API for media panel actions, timeline operations, and UI elements.

## Shared Libraries

*   **`pyflame_lib_frame_io.py`**: A shared library providing custom Flame-like UI widgets (using PySide2/PySide6), configuration management (`PyFlameConfig`), and various Flame utility functions. This library is used by the Frame.io scripts for UI and general helper tasks.
*   **`frame_io_utils.py`**: A utility module specific to this toolset that centralizes:
    *   Configuration loading for Frame.io settings.
    *   Common Frame.io API interaction functions (e.g., finding projects, assets, creating folders, updating statuses).
    *   Standardized error handling for Frame.io API calls.

## Configuration

All Frame.io scripts share a common configuration file:

*   **File Path**: `config/config.xml` (relative to the directory of each script).
*   **Creation**: If this file is missing when a script is run, a default version with placeholder values will be created automatically. You **must** edit this file to provide your actual Frame.io credentials.

**`config.xml` Structure and Keys:**

```xml
<settings>
    <frame_io_settings>
        <!-- Your Frame.io Developer Token. Replace the placeholder. -->
        <token>fio-x-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-xxxxxxxxxxx-xxxxxxxxxxx</token>
        <!-- Your Frame.io Account ID. -->
        <account_id>xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx</account_id>
        <!-- The ID of the Frame.io Team you want to work with. -->
        <team_id>xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx</team_id>
        <!-- Base path for local job folders (used by uploader scripts). -->
        <jobs_folder>/Volumes/vfx/UC_Jobs</jobs_folder>
        <!-- Full path to the H.264 export preset XML file for Flame. -->
        <preset_path_h264>/opt/Autodesk/shared/python/frame_io/presets/UC H264 10Mbits.xml</preset_path_h264>
    </frame_io_settings>
</settings>
```

**Important:**
*   Replace the placeholder `<token>` with your valid Frame.io Developer Token.
*   Update `<account_id>`, `<team_id>`, `<jobs_folder>`, and `<preset_path_h264>` to match your environment and needs.

## Installation

1.  Copy the script files (e.g., `frame_io_shot_uploader.py`, `frame_io_utils.py`, etc.) and the `pyflame_lib_frame_io.py` library into your Flame scripts directory (e.g., `/opt/Autodesk/shared/python/`). It's recommended to place them in a subdirectory like `/opt/Autodesk/shared/python/frame_io/`.
2.  Ensure the `frameioclient` Python library is installed in your Flame Python environment:
    ```bash
    pip install frameioclient
    ```
3.  Run one of the scripts from Flame. It will guide you if the `config/config.xml` file is missing or needs to be created and populated.

## Usage

The scripts are designed to be run as custom actions from the Flame Media Panel or Timeline, depending on the script:

*   **Shot Uploader**: Media Panel (select clips)
*   **Conform Uploader**: Media Panel (select clips)
*   **Get Comments**: Media Panel (select clips) or Timeline (select segments)
*   **Get Status**: Media Panel (select clips)
*   **Set Status**: Media Panel (select clips)

Refer to the comments at the top of each script file for more specific details on its usage and any version history.
