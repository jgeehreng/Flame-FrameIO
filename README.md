# FrameIO Integration for Autodesk Flame

A comprehensive integration suite for connecting Autodesk Flame with FrameIO, enabling seamless uploads, comment synchronization, and project management within the Uppercut VFX Pipeline.

## Overview

This package provides several Python scripts that integrate FrameIO's review and collaboration platform with Autodesk Flame. The integration supports:

- **Config Management**: Unified global and user configuration editor
- **Conform Uploads**: Automated upload of conform sequences to FrameIO
- **Shot Uploads**: Direct upload of shots/clips to FrameIO
- **Comment Synchronization**: Fetch comments from FrameIO and create Flame markers
- **Status Management**: Get and set FrameIO status labels on Flame clips
- **Automatic Versioning**: Smart version increment based on existing FrameIO assets

## Requirements

- **Autodesk Flame 2023.2 or later**
- **Python 3** (bundled with Flame)
- **FrameIO Token** (get one from [FrameIO Developer Portal](https://developer.frame.io/))
- **Required Python packages** (automatically installed via `frame_io_packages.py`):
  - `requests`
  - `frameioclient` (FrameIO Python SDK)

## Installation

1. **Copy the files** to your Flame Python scripts directory:
   ```
   /opt/Autodesk/shared/python/frame_io/
   ```
   Or for user-specific installation:
   ```
   ~/flame/python/frame_io/
   ```

2. **Ensure the directory structure** matches:
   ```
   frame_io/
   ├── lib/
   │   ├── __init__.py
   │   └── frame_io_api.py
   ├── config/
   │   └── shared_config.json
   ├── presets/
   │   └── (export presets)
   ├── frame_io_config_editor.py
   ├── frame_io_conform_uploader.py
   ├── frame_io_get_comments.py
   ├── frame_io_get_status.py
   ├── frame_io_set_status.py
   ├── frame_io_shot_uploader.py
   └── frame_io_csv_to_markers.py
   ```

3. **First-time setup**: Launch Flame and use the config editor to set up your FrameIO token, account ID, and team ID.

## Configuration

### Global Configuration

Global settings are stored at:
```
/opt/Autodesk/shared/python/frame_io/config/shared_config.json
```

**Global Settings:**
- `jobs_folder`: Base path for exported files (default: `/Volumes/vfx/UC_Jobs`)
- `preset_path_h264`: Path to H.264 export preset XML
- `project_token`: Which project identifier to use - `"nickname"` or `"name"` (default: `"nickname"`)
- `debug`: Enable verbose debug logging (default: `false`)
- `enable_file_logging`: Enable file logging to `~/flame/python/frame_io/logs/` (default: `false`)

### User Configuration

User-specific settings are stored at:
```
~/flame/python/frame_io/user_config.json
```

**User Settings:**
- `frame_io_token`: Your FrameIO API token (required)
- `frame_io_account_id`: Your FrameIO account ID (required)
- `frame_io_team_id`: Your FrameIO team ID (required)

### Config Editor

Access the configuration editor from Flame's main menu:
```
Main Menu → UC FrameIO → Edit Config
```

The editor provides:
- **Global Settings Tab**: Configure shared pipeline settings
- **User Settings Tab**: Configure your personal FrameIO token, account ID, and team
- **Token Validation**: Test your FrameIO token and auto-populate account/team info
- **Documentation Links**: Quick access to FrameIO API documentation

## Scripts

### 1. FrameIO Config Editor (`frame_io_config_editor.py`)

**Location**: Main Menu → UC FrameIO → Edit Config

A GUI tool for managing both global and user-specific FrameIO configuration. Features:
- Separate tabs for global and user settings
- Token validation with account/team auto-discovery
- Real-time configuration updates
- Support for both project nickname and name token modes

### 2. FrameIO Conform Uploader (`frame_io_conform_uploader.py`)

**Location**: Media Panel → UC FrameIO → Conform Uploader

Uploads selected sequences to FrameIO with automatic versioning:
- Exports sequences to H.264 format
- Automatically increments version numbers (e.g., `v01` → `v02`) if asset exists in FrameIO
- Creates organized folder structure: `FROM_FLAME/YYYY-MM-DD/HHMM/`
- Uploads to FrameIO project's CONFORMS folder
- Progress tracking with detailed status updates

**Usage:**
1. Select one or more sequences in the Media Panel
2. Right-click → UC FrameIO → Conform Uploader
3. Confirm the upload
4. Monitor progress in the progress window

### 3. FrameIO Shot Uploader (`frame_io_shot_uploader.py`)

**Location**: Media Panel → UC FrameIO → Shot Uploader

Uploads selected clips/shots directly to FrameIO:
- Exports clips to H.264 format
- Automatically creates version stacks if matching base name found
- Uploads to FrameIO project's SHOTS folder
- Supports version pattern matching (e.g., `_v01`, `_V01`)

**Usage:**
1. Select one or more clips in the Media Panel
2. Right-click → UC FrameIO → Shot Uploader
3. Files are exported and uploaded automatically

### 4. FrameIO Get Comments (`frame_io_get_comments.py`)

**Location**: 
- Media Panel → UC FrameIO → Get Comments (for sequences)
- Timeline → UC FrameIO → Get Comments (for segments)

Fetches comments from FrameIO and creates Flame markers:
- Searches FrameIO for assets matching sequence/clip names
- Creates markers at comment timestamps
- Includes comment text, author, and replies
- Colors clips/segments with "Address Comments" label
- Supports both sequences and timeline segments
- Caches comments per sequence to avoid duplicate API calls

**Usage:**
1. Select sequences in Media Panel or segments in Timeline
2. Right-click → UC FrameIO → Get Comments
3. Markers are automatically created with comment details

### 5. FrameIO Get Status (`frame_io_get_status.py`)

**Location**: Media Panel → UC FrameIO → Get Status

Fetches status labels from FrameIO and applies color coding:
- Maps FrameIO statuses to Flame color labels:
  - `approved` → "Approved" (green)
  - `needs_review` → "Needs Review" (orange)
  - `in_progress` → "In Progress" (blue)

**Usage:**
1. Select clips in Media Panel
2. Right-click → UC FrameIO → Get Status
3. Clips are colored based on their FrameIO status

### 6. FrameIO Set Status (`frame_io_set_status.py`)

**Location**: Media Panel → UC FrameIO → Set Status

Sets FrameIO status labels based on Flame color labels:
- Maps Flame color labels to FrameIO statuses:
  - "Approved" → `approved`
  - "Needs Review" → `needs_review`
  - "In Progress" → `in_progress`

**Usage:**
1. Apply color labels to clips in Flame
2. Select clips in Media Panel
3. Right-click → UC FrameIO → Set Status
4. FrameIO status is updated to match Flame color labels

### 7. CSV to Markers (`frame_io_csv_to_markers.py`)

**Location**: 
- Media Panel → UC FrameIO → CSV → Timeline Markers
- Timeline → UC FrameIO → CSV → Segment Markers

Imports a CSV file exported from FrameIO and adds markers to clips:
- No need to modify the CSV downloaded from FrameIO
- Supports both timeline markers and segment markers
- Includes comment text and author information

**Usage:**
1. Export comments CSV from FrameIO
2. Select a clip or segment
3. Right-click → UC FrameIO → CSV → Timeline Markers (or Segment Markers)
4. Navigate to the CSV file
5. Markers are automatically created

## Features

### Automatic Versioning

Both uploader scripts support automatic version increment:
- Searches FrameIO for existing assets with matching base name
- If found, automatically increments version number (e.g., `v01` → `v02`)
- Works with both lowercase (`v01`) and uppercase (`V01`) version patterns

### Comment Caching

The Get Comments script caches comments per sequence name to avoid duplicate API calls when processing multiple segments from the same sequence.

### Error Handling & Retry Logic

All API operations include:
- Automatic retry with exponential backoff for network errors
- User-friendly error messages with actionable guidance
- Detailed error logging for debugging
- Graceful handling of server errors (429, 500, 502, 503, 504)

### File Logging

Optional file logging for debugging:
- Logs saved to `~/flame/python/frame_io/logs/`
- Daily log files with timestamps
- Includes debug, info, warning, and error levels
- Enable via Config Editor → Global Settings → File Logging

### Progress Tracking

Both uploader scripts include progress indicators:
- Real-time progress bars
- File-by-file status updates
- Overall completion tracking

### Backward Compatibility

The system maintains backward compatibility with XML config files:
- Automatically migrates XML configs to JSON format
- Falls back to XML if JSON doesn't exist
- Supports both old and new config field names

## Troubleshooting

### Config Issues

- **Missing token/account/team**: Use the Config Editor (Main Menu → UC FrameIO → Edit Config) to set up your credentials
- **Invalid token**: Use the "Validate Token" button in the Config Editor to test your token
- **Configuration errors**: Check error messages for specific missing fields and use the Config Editor to fix them

### Upload Issues

- **Export preset not found**: Check that `preset_path_h264` in config points to a valid preset file
- **Upload fails**: Verify your FrameIO token has proper permissions for the project
- **Network errors**: The system will automatically retry failed uploads. Check logs for detailed error information
- **Permission denied**: Ensure your FrameIO token has permission to create projects and upload files in the specified team

### Comment Issues

- **No comments found**: Ensure sequence/clip names exactly match FrameIO asset names
- **Markers in wrong place**: Check that frame rates match between Flame and FrameIO

### Debugging

- **Enable debug mode**: Use Config Editor → Global Settings → Debug Mode for verbose console output
- **Enable file logging**: Use Config Editor → Global Settings → File Logging to save detailed logs to disk
- **Check log files**: Logs are saved to `~/flame/python/frame_io/logs/` with daily rotation

## Migration from XML Config

If you have an existing XML config file, the system will automatically migrate it to JSON format on first run. The XML file is preserved as a backup.

## Support

For issues or questions, contact the Uppercut VFX Pipeline team.

