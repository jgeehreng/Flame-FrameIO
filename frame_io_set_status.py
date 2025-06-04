'''
Script Name: frame_io_set_status
Script Version: 0.3
Flame Version: 2025.1
Written by: John Geehreng
Creation Date: 09.11.24
Update Date: 09.11.24 (Refactored to use frame_io_utils.py)

Custom Action Type: Media Panel

Description:

    This script will set the status of any items in FrameIO based on the color label(s)
    of the Flame selection.

To install:

    Copy script into /opt/Autodesk/shared/python/frame_io
    Ensure frame_io_utils.py is also in this directory.

Updates:
(Refactored to use frame_io_utils.py)
09.11.24 - v0.2 - Added Try/Except for Colour Labels.
09.06.24 - v0.1 - Inception
'''

import xml.etree.ElementTree as ET # Not strictly needed if config is fully handled by utils
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
    find_frame_io_asset_by_name,
    update_asset_label # Added
)

SCRIPT_NAME = 'FrameIO Set Status'
SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
VERSION = 'v0.3' # Incremented version

#-------------------------------------#
# Main Script

class frame_io_set_status(object):

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
        # These are loaded for consistency but not strictly used by this script's core logic
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

        self.sync_flame_statuses_to_frameio(selection)

    # local config() and catch_exception decorator removed, using frame_io_utils.py versions

    @frame_io_api_exception_handler
    def sync_flame_statuses_to_frameio(self, selection):
        print(f"{SCRIPT_NAME}: Starting to sync Flame statuses to Frame.io...")
        self.project_nickname = flame.projects.current_project.nickname
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

            new_label = None
            if selection_color_label == "Approved":
                new_label = 'approved'
            elif selection_color_label == "Needs Review":
                new_label = 'needs_review'
            elif selection_color_label == "In Progress":
                new_label = 'in_progress'
            # Consider "Rejected" if Frame.io supports it and it's a desired mapping
            # elif selection_color_label == "Rejected":
            #     new_label = 'rejected'
            else:
                message = f"Flame item '{selection_name}' has color label '{selection_color_label}', which does not map to a recognized Frame.io status (Approved, Needs Review, In Progress). Skipping."
                flame.messages.show_in_console(message, 'info', 5)
                print(message)
                continue

            print(f"Attempting to set Frame.io status to: '{new_label}'")

            # Use find_frame_io_asset_by_name from utils
            asset_info = find_frame_io_asset_by_name(self.client, project_id, selection_name, self.team_id, self.account_id, SCRIPT_NAME=SCRIPT_NAME)

            if asset_info and 'id' in asset_info:
                asset_id = asset_info['id']
                current_fio_label = asset_info.get('label')
                print(f"Found Frame.io asset '{selection_name}' (ID: {asset_id}, Current Status: {current_fio_label})")

                if current_fio_label == new_label:
                    message = f"Asset '{selection_name}' in Frame.io already has status '{new_label}'. No update needed."
                    print(message)
                    flame.messages.show_in_console(message, 'info', 3)
                    continue

                # Use update_asset_label from utils
                update_success = update_asset_label(self.client, asset_id, new_label, SCRIPT_NAME)
                if update_success: # update_asset_label returns True on success, None on failure (decorator handles dialog)
                    print(f"Successfully updated Frame.io status for asset '{selection_name}' (ID: {asset_id}) to '{new_label}'.")
                    flame.messages.show_in_console(f"Updated '{selection_name}' status to '{new_label}' in Frame.io.", 'info', 3)
                # else: Error dialog handled by decorator in update_asset_label

            else:
                message = f"Asset '{selection_name}' not found in Frame.io project '{self.project_nickname}'. Cannot set status."
                flame.messages.show_in_console(message, 'info', 6)
                print(message)
                continue
        
        print(f'\n{">" * 10} {SCRIPT_NAME} {VERSION} End {"<" * 10}\n')

    # Local helper methods get_fio_projects and find_a_fio_asset are removed.

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
                    'name': 'Set Status',
                    'order': 6,
                    'isVisible': scope_clip,
                    'separator': 'above',
                    'execute': frame_io_set_status, # Class name is the callable
                    'minimumVersion': '2025.1'
                }
            ]
        }
    ]
