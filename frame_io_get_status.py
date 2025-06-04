'''
Script Name: frame_io_get_status
Script Version: 0.3
Flame Version: 2025.1
Written by: John Geehreng
Creation Date: 09.06.24
Update Date: 09.11.24 (Refactored to use frame_io_utils.py)

Custom Action Type: Media Panel

Description:

    This script will fetch the status of any items in FrameIO and color code
    the Flame selection according to the status on FrameIO.

To install:

    Copy script into /opt/Autodesk/shared/python/frame_io
    Ensure frame_io_utils.py is also in this directory.

Updates:
(Refactored to use frame_io_utils.py)
09.11.24 - v0.2 - Added Try/Except for Colour Labels.
09.06.24 - v0.1 - Inception
'''

import xml.etree.ElementTree as ET # Keep for now, though utils might make it redundant here
import flame
import os
import traceback
from frameioclient import FrameioClient, errors as frameio_errors

# Import utilities from frame_io_utils.py
from frame_io_utils import (
    load_frame_io_config,
    create_default_frame_io_config,
    ConfigurationError,
    frame_io_api_exception_handler,
    get_frame_io_project_details,
    find_frame_io_asset_by_name
)

SCRIPT_NAME = 'FrameIO Get Status'
SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
VERSION = 'v0.3' # Incremented version

#-------------------------------------#
# Main Script

class frame_io_get_status(object):

    def __init__(self, selection):
        print(f'\n{">" * 10} {SCRIPT_NAME} {VERSION} Start {"<" * 10}\n')

        self.config_xml = os.path.join(SCRIPT_PATH, 'config', 'config.xml')
        self.project_nickname = flame.projects.current_project.nickname
        self.client = None

        try:
            config_data = load_frame_io_config(self.config_xml, SCRIPT_NAME)
        except ConfigurationError as e:
            print(f"Configuration error: {e}. Attempting to create a default config file.")
            flame.messages.show_in_dialog(
                f"{SCRIPT_NAME} Info",
                f"Configuration issue: {e}\n\nA default config file will be created at:\n{self.config_xml}\n\nPlease update it with your Frame.io credentials and run the script again.",
                type="info"
            )
            if create_default_frame_io_config(self.config_xml, SCRIPT_NAME, SCRIPT_PATH):
                print("Default config created. Please update it and rerun the script.")
            else:
                print("Failed to create default config file.")
            return
        except Exception as e:
             flame.messages.show_in_dialog(f"{SCRIPT_NAME} Critical Error", f"An unexpected error occurred while loading configuration: {e}", type="error")
             traceback.print_exc()
             return

        if not config_data:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Critical Error", "Configuration could not be loaded. Please check logs.", type="error")
            return

        self.token = config_data.get('token')
        self.account_id = config_data.get('account_id')
        self.team_id = config_data.get('team_id')
        # jobs_folder and preset_path_h264 are not used by this script but loaded by util for consistency
        self.jobs_folder = config_data.get('jobs_folder')
        self.preset_path_h264 = config_data.get('preset_path_h264')

        if not self.token or self.token.startswith('fio-x-xxxxxx'):
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Frame.io token in {self.config_xml} is missing or is a placeholder. Please update it and run the script again.", type="error")
            return

        try:
            self.client = FrameioClient(self.token)
            print("Frame.io client initialized.")
        except Exception as e:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to initialize Frame.io client: {e}\nEnsure your token in config.xml is valid.", type="error")
            print(f"Error initializing Frame.io client: {e}")
            traceback.print_exc()
            return

        self.sync_frameio_statuses_to_flame(selection)

    # local config() method removed, using frame_io_utils.load_frame_io_config
    # local catch_exception decorator removed, using frame_io_utils.frame_io_api_exception_handler

    @frame_io_api_exception_handler
    def sync_frameio_statuses_to_flame(self, selection):
        print(f"{SCRIPT_NAME}: Starting to sync Frame.io statuses to Flame...")
        self.project_nickname = flame.projects.current_project.nickname # Ensure it's current
        print(f"Current Flame project nickname: {self.project_nickname}")

        project_details = get_frame_io_project_details(self.client, self.project_nickname, self.team_id, SCRIPT_NAME)
        if not project_details:
            # Dialog/logging handled by decorated get_frame_io_project_details
            print(f"Aborting status sync as Frame.io project '{self.project_nickname}' could not be accessed.")
            return

        project_id = project_details['project_id']
        print(f"Using Frame.io project ID: {project_id}")

        for item_index, item in enumerate(selection):
            if item_index > 0: print('\n')

            selection_name = str(item.name).strip("'")
            print(f"Processing Flame item: '{selection_name}'")

            try:
                selection_color_label = item.colour_label.get_value()
            except AttributeError:
                 selection_color_label = str(item.colour_label)
            print(f"Flame item color label: '{selection_color_label}'")

            # This script *gets* status from Frame.io to *set* Flame color labels.
            # The logic for mapping Flame color labels to Frame.io new_label is for frame_io_set_status.py.
            # Here, we need to get the label from Frame.io.

            asset_info = find_frame_io_asset_by_name(self.client, project_id, selection_name, self.team_id, self.account_id, SCRIPT_NAME=SCRIPT_NAME)

            if asset_info and 'id' in asset_info:
                asset_id = asset_info['id']
                frame_io_status = asset_info.get('label') # This is the status from Frame.io
                print(f"Found Frame.io asset '{selection_name}' (ID: {asset_id}, Frame.io Status: {frame_io_status})")

                if frame_io_status:
                    new_flame_color_label = None
                    new_flame_color_rgb = None # For older Flame versions

                    if frame_io_status == 'approved':
                        new_flame_color_label = "Approved"
                        new_flame_color_rgb = (0.11372549086809158, 0.26274511218070984, 0.1764705926179886) # Greenish
                    elif frame_io_status == 'needs_review':
                        new_flame_color_label = "Needs Review"
                        new_flame_color_rgb = (0.6000000238418579, 0.3450980484485626, 0.16470588743686676) # Orange/Yellow
                    elif frame_io_status == 'in_progress':
                        new_flame_color_label = "In Progress"
                        new_flame_color_rgb = (0.26274511218070984, 0.40784314274787903, 0.5019607543945312) # Blueish
                    # Add other Frame.io status -> Flame label mappings if necessary

                    if new_flame_color_label:
                        try:
                            if item.colour_label.get_value() == new_flame_color_label:
                                print(f"Flame item '{selection_name}' already has status/color label '{new_flame_color_label}'. No change needed.")
                            else:
                                item.colour_label = new_flame_color_label
                                print(f"Successfully set Flame color label for '{selection_name}' to '{new_flame_color_label}'.")
                        except AttributeError: # Fallback for older Flame versions
                            # Note: Comparing RGB colors can be tricky due to precision.
                            # This is a simple check; more robust might involve comparing within a tolerance.
                            current_rgb = tuple(item.colour) if hasattr(item, 'colour') else None
                            if current_rgb and new_flame_color_rgb and \
                               all(abs(a-b) < 0.001 for a, b in zip(current_rgb, new_flame_color_rgb)):
                                print(f"Flame item '{selection_name}' already has equivalent RGB color for status '{frame_io_status}'. No change needed.")
                            elif new_flame_color_rgb:
                                item.colour = new_flame_color_rgb
                                print(f"Successfully set Flame RGB color for '{selection_name}' for status '{frame_io_status}'.")
                            else:
                                print(f"No specific RGB mapping for Frame.io status '{frame_io_status}'. Color not changed.")
                    else:
                        message = f"Frame.io status '{frame_io_status}' for asset '{selection_name}' does not map to a configured Flame color label. Color not changed."
                        flame.messages.show_in_console(message, 'info', 5)
                        print(message)
                else: # Asset found but has no status (label is None or empty)
                    message = f"Asset '{selection_name}' found in Frame.io but has no status assigned. Flame color label not changed."
                    flame.messages.show_in_dialog(f"{SCRIPT_NAME} Info", message, type="info")
                    print(message)

            else: # Asset not found
                message = f"Asset '{selection_name}' not found in Frame.io project '{self.project_nickname}'. Cannot get status."
                flame.messages.show_in_console(message, 'info', 6)
                print(message)
                continue

        print(f'\n{">" * 10} {SCRIPT_NAME} {VERSION} End {"<" * 10}\n')

    # Local helper methods get_fio_projects and find_a_fio_asset are removed
    # as their functionality is now provided by frame_io_utils.py

# Scope
def scope_clip(selection):
    # import flame # Not needed, flame is globally imported
    for item in selection:
        if isinstance(item, flame.PyClip):
            return True
    return False

def scope_segment(selection):
    # import flame # Not needed, flame is globally imported
    for item in selection:
        if isinstance(item, flame.PySegment):
            return True
    return False
#-------------------------------------#
# Flame Menus

def get_media_panel_custom_ui_actions():
    return [
        {
            'name': 'UC FrameIO',
            'actions': [
                {
                    'name': 'Get Status',
                    'order': 5,
                    'isVisible': scope_clip,
                    'separator': 'above',
                    'execute': frame_io_get_status, # Class name is the callable
                    'minimumVersion': '2025.1'
                }
            ]
        }
    ]
