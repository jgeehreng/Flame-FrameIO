'''
Script Name: frame_io_shot_uploader
Script Version: 0.9.4
Flame Version: 2024.2
Written by: John Geehreng
Creation Date: 01.03.23
Update Date: 12.18.24 (Refactored to use frame_io_utils.py)

Custom Action Type: Media Panel

Description:

    This script will export h264 .mp4's to a FROM_FLAME folder in your job folder,
    save it to a FROM_FLAME shared library, and upload them to FrameIO.
    It will also automatically create or add to version stacks if it can find a matching base name.
    Script assumes a verion of _v## or _V### in order to match file names.

To install:

    Copy script into /opt/Autodesk/shared/python/frame_io
    Ensure frame_io_utils.py is also in this directory.

'''

import xml.etree.ElementTree as ET
import flame
import datetime
import os
import subprocess
import re
import glob
import traceback
from frameioclient import FrameioClient, errors as frameio_errors

# Import utilities from frame_io_utils.py
from frame_io_utils import (
    load_frame_io_config,
    create_default_frame_io_config,
    ConfigurationError,
    frame_io_api_exception_handler,
    get_frame_io_project_details, # Added
    find_frame_io_asset_by_name,  # Added
    create_frame_io_project,      # Added
    create_frame_io_folder,       # Added
    add_version_to_asset          # Added
)

SCRIPT_NAME = 'FrameIO Shot Uploader'
SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
VERSION = 'v0.9.4' # Incremented version

#-------------------------------------#
# Main Script

class frame_io_uploader(object):

    def __init__(self, selection):
        print(f'\n{">" * 10} {SCRIPT_NAME} {VERSION} Start {"<" * 10}\n')

        self.config_xml = os.path.join(SCRIPT_PATH, 'config', 'config.xml')
        self.project_nickname = flame.projects.current_project.nickname
        self.client = None
        self.new_folder_id = None # Initialize to ensure it exists

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

        self.export_mp4(selection)
        if hasattr(self, 'export_dir') and self.export_dir:
            self.upload_to_frameio()
        else:
            print("Export directory not set, skipping Frame.io upload.")
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Info", "Export process did not complete or export directory was not set. Skipping Frame.io upload.", type="info")
    
    @frame_io_api_exception_handler
    def export_mp4(self, selection):
        self.project_name = flame.projects.current_project.name
        dateandtime = datetime.datetime.now()
        today = (dateandtime.strftime("%Y-%m-%d"))
        time = (dateandtime.strftime("%H%M"))

        if not self.preset_path_h264 or not os.path.isfile(self.preset_path_h264):
            error_msg = f"Cannot find Export Preset: {self.preset_path_h264 or 'Path not configured'}"
            print(error_msg)
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", error_msg, type="error")
            self.export_dir = None
            return

        print(f"Export Preset Found: {self.preset_path_h264}")
        self.export_dir = os.path.join(
            str(self.jobs_folder), str(self.project_nickname), "FROM_FLAME", str(today), str(time)
        )
        print(f"Target export directory: {self.export_dir}")
        try:
            os.makedirs(self.export_dir, exist_ok=True)
            print(f"Ensured directory exists: {self.export_dir}")
        except OSError as e:
            message = f"Could not create directory: {self.export_dir}\nError: {e}"
            print(message)
            flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Directory Creation Error", message, type="error")
            self.export_dir = None
            return

        exporter = flame.PyExporter()
        exporter.foreground = True
        exporter.export_between_marks = False
        exporter.use_top_video_track = True
        print(f"Starting export of {len(selection)} items...")
        for item in selection:
            print(f"Exporting item: {item.name.get_value() if hasattr(item.name, 'get_value') else item.name}")
            exporter.export(item, self.preset_path_h264, self.export_dir)
        print("All items processed for export.")
    
    @frame_io_api_exception_handler
    def upload_to_frameio(self):
        print("Starting Frame.io upload process...")
        print(f"Processing for Flame project: {self.project_nickname}")

        project_details = get_frame_io_project_details(self.client, self.project_nickname, self.team_id, SCRIPT_NAME)

        root_asset_id = None
        project_id = None

        if project_details:
            root_asset_id = project_details.get('root_asset_id')
            project_id = project_details.get('project_id')
            # Try to find SHOTS folder if project exists
            shots_folder_asset = find_frame_io_asset_by_name(self.client, project_id, "SHOTS", self.team_id, self.account_id, asset_type='folder', SCRIPT_NAME=SCRIPT_NAME)
            if shots_folder_asset:
                self.new_folder_id = shots_folder_asset['id'] # Set context for uploads
                print(f"Found existing 'SHOTS' folder with ID: {self.new_folder_id}")
            else:
                print(f"Warning: 'SHOTS' folder not found in existing project '{self.project_nickname}'. Will be created if needed.")
                self.new_folder_id = None

        if not project_id:
            print(f"Frame.io project '{self.project_nickname}' not found. Attempting to create it.")
            project_creation_info = create_frame_io_project(self.client, self.project_nickname, self.team_id, SCRIPT_NAME)
            if not project_creation_info:
                print(f"Failed to create Frame.io project '{self.project_nickname}'. Halting upload.")
                return
            root_asset_id = project_creation_info.get('root_asset_id')
            project_id = project_creation_info.get('project_id')
            if not project_id:
                 flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Could not obtain a valid project ID for '{self.project_nickname}' after creation attempt. Halting upload.", type="error")
                 return
            # After project creation, create default folders including SHOTS
            create_frame_io_folder(self.client, root_asset_id, "CONFORMS", SCRIPT_NAME) # Create CONFORMS
            shots_folder_data = create_frame_io_folder(self.client, root_asset_id, "SHOTS", SCRIPT_NAME) # Create SHOTS
            if shots_folder_data:
                self.new_folder_id = shots_folder_data['id'] # This is the ID of the newly created SHOTS folder
                print(f"'SHOTS' folder created with ID: {self.new_folder_id}")
            else:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to create 'SHOTS' folder for new project '{self.project_nickname}'. Halting upload.", type="error")
                return


        print(f"Using Frame.io Project ID: {project_id}, Root Asset ID: {root_asset_id}")
        self.root_asset_id = root_asset_id

        self.export_path_glob = os.path.join(self.export_dir, '*')
        files_to_upload = glob.glob(self.export_path_glob)
        files_to_upload = [f for f in files_to_upload if os.path.isfile(f)]

        if not files_to_upload:
            print(f"No files found in {self.export_dir} to upload.")
            flame.messages.show_in_dialog(f"{SCRIPT_NAME}", f"No files found in the export directory: {self.export_dir}", type="info")
            return

        for filename_full_path in files_to_upload:
            print('\n')
            _path, file_name_only = os.path.split(filename_full_path)
            print(f"Processing file: {filename_full_path}")
            print(f"File name: {file_name_only}")

            pattern = r'_[a-zA-Z]*?_[vV]\d+'
            base_name_for_search = re.split(pattern, file_name_only)[0]
            print(f"Base name for Frame.io search: {base_name_for_search}")

            asset_info = find_frame_io_asset_by_name(self.client, project_id, base_name_for_search, self.team_id, self.account_id, asset_type='file', SCRIPT_NAME=SCRIPT_NAME)

            existing_asset_id, asset_type, existing_asset_parent_id = None, None, None
            if asset_info:
                 asset_type = asset_info.get('type')
                 existing_asset_id = asset_info.get('id')
                 existing_asset_parent_id = asset_info.get('parent_id')

            if existing_asset_id:
                if asset_type == 'file':
                    print(f"Found existing file asset: {existing_asset_id}. Uploading as new version.")
                    newly_uploaded_asset_info = self.client.assets.upload(existing_asset_parent_id, filename_full_path) # Direct SDK call
                    if newly_uploaded_asset_info and 'id' in newly_uploaded_asset_info:
                        add_version_to_asset(self.client, existing_asset_id, newly_uploaded_asset_info['id'], SCRIPT_NAME)
                elif asset_type == 'version_stack':
                    print(f"Found version stack: {existing_asset_id}. Uploading asset to stack.")
                    self.client.assets.upload(existing_asset_id, filename_full_path) # Direct SDK call
                else:
                    print(f"Warning: Found asset {existing_asset_id} but it's of unexpected type '{asset_type}'. Attempting to upload to SHOTS folder.")
                    existing_asset_id = None

            if not existing_asset_id:
                print(f"No existing match for '{base_name_for_search}'. Uploading as new asset to 'SHOTS' folder.")

                target_shots_folder_id = self.new_folder_id

                if not target_shots_folder_id:
                    print("self.new_folder_id (SHOTS folder ID) not set. Attempting to find or create SHOTS folder again.")
                    shots_folder_asset = find_frame_io_asset_by_name(self.client, project_id, "SHOTS", self.team_id, self.account_id, asset_type='folder', SCRIPT_NAME=SCRIPT_NAME)
                    if shots_folder_asset:
                        target_shots_folder_id = shots_folder_asset['id']
                    else:
                        print("'SHOTS' folder still not found. Creating it now.")
                        created_shots_folder_data = create_frame_io_folder(self.client, self.root_asset_id, "SHOTS", SCRIPT_NAME)
                        if created_shots_folder_data:
                            target_shots_folder_id = created_shots_folder_data['id']
                        else:
                             flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to find or create 'SHOTS' folder in project {self.project_nickname}. Skipping upload for {file_name_only}.", type="error")
                             continue

                if target_shots_folder_id:
                    print(f"Uploading '{file_name_only}' to 'SHOTS' folder (ID: {target_shots_folder_id}).")
                    self.client.assets.upload(target_shots_folder_id, filename_full_path) # Direct SDK call
                else:
                    flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Could not determine target SHOTS folder for {file_name_only}. Upload skipped.", type="error")

        print(f"\n{'>' * 10} {SCRIPT_NAME} {VERSION} End {'<' * 10}\n")

    # Local helper methods are now removed as their logic is delegated to frame_io_utils.py
    # or directly handled in upload_to_frameio using SDK calls where appropriate.

# Scope
def scope_clip(selection):
    for item in selection:
        if isinstance(item, flame.PyClip):
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
                    'name': 'Shot Uploader',
                    'order': 1,
                    'isVisible': scope_clip,
                    'execute': frame_io_uploader,
                    'minimumVersion': '2024.2'
                }
            ]
        }
    ]
