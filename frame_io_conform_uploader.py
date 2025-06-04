'''
Script Name: frame_io_conform_uploader
Script Version: 1.3
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

try:
    from PySide6 import QtWidgets
except ImportError:
    from PySide2 import QtWidgets
import xml.etree.ElementTree as ET
import flame
import datetime
import traceback
import os
import re
import glob
from frameioclient import FrameioClient, errors as frameio_errors
from pyflame_lib_frame_io import PyFlameProgressWindow # Assuming this is still used

# Import utilities from frame_io_utils.py
from frame_io_utils import (
    load_frame_io_config,
    create_default_frame_io_config,
    ConfigurationError,
    frame_io_api_exception_handler,
    get_frame_io_project_details,
    find_frame_io_asset_by_name,
    create_frame_io_project,
    create_frame_io_folder,
    add_version_to_asset
)

SCRIPT_NAME = 'FrameIO Conform Uploader'
SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
VERSION = 'v1.3' # Incremented version

#-------------------------------------#
# Main Script

class frame_io_uploader(object):

    def __init__(self, selection):
        print(f'\n{">" * 10} {SCRIPT_NAME} {VERSION} Start {"<" * 10}\n')

        self.config_xml = os.path.join(SCRIPT_PATH, 'config', 'config.xml')
        self.project_nickname = flame.projects.current_project.nickname
        self.client = None
        self.new_folder_id = None # Initialize to ensure it exists, primarily for CONFORMS folder

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

        self.version_upper(selection)
        self.export_and_copy_path(selection)

        if hasattr(self, 'export_path') and self.export_path:
            self.upload_to_frameio()
        else:
            print("Export directory not set or export failed, skipping Frame.io upload.")
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Info", "Export process did not complete or export directory was not set. Skipping Frame.io upload.", type="info")

    @frame_io_api_exception_handler
    def export_and_copy_path(self, selection):
        self.project_name = flame.projects.current_project.name
        dateandtime = datetime.datetime.now()
        today = (dateandtime.strftime("%Y-%m-%d"))
        time = (dateandtime.strftime("%H%M"))
        shared_libs = flame.projects.current_project.shared_libraries
        
        sharedlib = None
        for libary in shared_libs:      
            if libary.name == "FROM_FLAME":
                sharedlib = libary
        if not sharedlib:
            try:
                sharedlib = flame.projects.current_project.create_shared_library('FROM_FLAME')
                print("Created 'FROM_FLAME' shared library.")
            except Exception as e:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to create 'FROM_FLAME' shared library: {e}", type="error")
                self.export_path = None
                return

        if not self.preset_path_h264 or not os.path.isfile(self.preset_path_h264):
            error_msg = f"Cannot find Export Preset: {self.preset_path_h264 or 'Path not configured'}"
            print(error_msg)
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", error_msg, type="error")
            self.export_path = None
            return

        print(f"Export Preset Found: {self.preset_path_h264}")
        export_base_dir = os.path.join(str(self.jobs_folder), str(self.project_nickname), "FROM_FLAME")
        export_dir_with_date = os.path.join(export_base_dir, str(today))

        try:
            os.makedirs(export_dir_with_date, exist_ok=True)
            print(f"Ensured export directory exists: {export_dir_with_date}")
        except OSError as e:
            message = f"Could not create export directory: {export_dir_with_date}\nError: {e}"
            print(message)
            flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Directory Creation Error", message, type="error")
            self.export_path = None
            return

        exporter = flame.PyExporter()
        exporter.foreground = True
        exporter.export_between_marks = True
        exporter.use_top_video_track = True

        todays_match_folder = None
        for folder_item in sharedlib.folders:
            if folder_item.name == today:
                todays_match_folder = folder_item
                break
        
        postingfolder = None
        try:
            sharedlib.acquire_exclusive_access()
            if todays_match_folder:
                print(f"Found today's date folder: {today}")
                postingfolder = todays_match_folder.create_folder(time)
            else:
                print(f"Today's date folder '{today}' not found. Creating it.")
                today_folder = sharedlib.create_folder(today)
                postingfolder = today_folder.create_folder(time)

            if not postingfolder:
                raise Exception("Failed to create or access posting folder in shared library.")

            tab = flame.get_current_tab()
            if tab == 'MediaHub':
                flame.set_current_tab("Timeline")
            for item in selection:
                flame.media_panel.copy(item, postingfolder)
            
            exporter.export(postingfolder, self.preset_path_h264, export_dir_with_date)

            sharedlib.expanded = False
            if hasattr(postingfolder, 'expanded'): postingfolder.expanded = False
            if hasattr(postingfolder, 'parent') and hasattr(postingfolder.parent, 'expanded'):
                postingfolder.parent.expanded = False
        except Exception as e:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Error during shared library operations or export: {e}", type="error")
            traceback.print_exc()
            self.export_path = None
            return # Do not proceed if export failed
        finally:
             if sharedlib.exclusive_access():
                sharedlib.release_exclusive_access()

        if postingfolder and hasattr(postingfolder, 'name'):
            posted_folder_name_cleaned = str(postingfolder.name).strip("'")
            self.export_path = os.path.join(export_dir_with_date, posted_folder_name_cleaned)
            print(f"Exported to: {self.export_path}")
            qt_app_instance = QtWidgets.QApplication.instance()
            if qt_app_instance:
                qt_app_instance.clipboard().setText(self.export_path)
            else:
                print("Warning: QApplication instance not found. Could not copy export path to clipboard.")
        else:
            print("Error: Posting folder was not properly defined. Cannot set export path.")
            self.export_path = None

    @frame_io_api_exception_handler
    def upload_to_frameio(self):
        print("Starting Frame.io upload process...")
        print(f"Processing for Flame project: {self.project_nickname}")

        project_details = get_frame_io_project_details(self.client, self.project_nickname, self.team_id, SCRIPT_NAME)
        
        root_asset_id = None
        project_id = None
        self.new_folder_id = None # Reset for this context (CONFORMS folder)

        if project_details:
            root_asset_id = project_details.get('root_asset_id')
            project_id = project_details.get('project_id')
            conforms_folder_asset = find_frame_io_asset_by_name(self.client, project_id, "CONFORMS", self.team_id, self.account_id, asset_type='folder', SCRIPT_NAME=SCRIPT_NAME)
            if conforms_folder_asset:
                self.new_folder_id = conforms_folder_asset['id']
                print(f"Found existing 'CONFORMS' folder with ID: {self.new_folder_id}")
            else:
                print(f"Warning: 'CONFORMS' folder not found in existing project '{self.project_nickname}'. Will be created if needed.")

        if not project_id:
            print(f"Frame.io project '{self.project_nickname}' not found. Attempting to create it.")
            project_creation_info = create_frame_io_project(self.client, self.project_nickname, self.team_id, SCRIPT_NAME)
            if not project_creation_info:
                return
            root_asset_id = project_creation_info.get('root_asset_id')
            project_id = project_creation_info.get('project_id')
            if not project_id:
                 flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Could not get project ID after creation for '{self.project_nickname}'.", type="error")
                 return
            # Create default folders: SHOTS then CONFORMS. self.new_folder_id will be CONFORMS.
            create_frame_io_folder(self.client, root_asset_id, "SHOTS", SCRIPT_NAME)
            conforms_folder_data = create_frame_io_folder(self.client, root_asset_id, "CONFORMS", SCRIPT_NAME)
            if conforms_folder_data:
                self.new_folder_id = conforms_folder_data['id']
                print(f"'CONFORMS' folder created with ID: {self.new_folder_id}")
            else:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to create 'CONFORMS' folder for new project '{self.project_nickname}'.", type="error")
                return

        print(f"Using Frame.io Project ID: {project_id}, Root Asset ID: {root_asset_id}")
        self.root_asset_id = root_asset_id

        if not hasattr(self, 'export_path') or not self.export_path or not os.path.isdir(self.export_path):
             flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Upload error: Export path is invalid or not set ('{getattr(self, 'export_path', 'Not set')}').", type="error")
             return

        glob_pattern = os.path.join(self.export_path, '*')
        files_to_upload = glob.glob(glob_pattern)
        files_to_upload = [f for f in files_to_upload if os.path.isfile(f)]

        if not files_to_upload:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME}", f"No files found to upload in {self.export_path}.", type="info")
            return

        number_of_files = len(files_to_upload)
        files_uploaded_count = 0
        progress_window_instance = None
        try:
            progress_window_instance = PyFlameProgressWindow(
                num_to_do=number_of_files, title='Frame.io Conform Uploading...',
                text=f'Starting upload of {number_of_files} file(s)...', enable_done_button=False
            )
        except Exception as e:
            print(f"Error initializing progress window: {e}")
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Warning", "Could not initialize progress window. Upload will continue without UI progress.", type="warning")

        for filename_full_path in files_to_upload:
            files_uploaded_count += 1
            current_file_name = os.path.basename(filename_full_path)
            print(f"\nProcessing file {files_uploaded_count}/{number_of_files}: {filename_full_path}")

            if progress_window_instance:
                progress_window_instance.set_text(f'Uploading: {current_file_name} ({files_uploaded_count} of {number_of_files})')
                progress_window_instance.set_progress_value(files_uploaded_count)

            pattern = r'(_[vV]\d+)'
            matches = list(re.finditer(pattern, current_file_name))
            base_name_for_search = os.path.splitext(current_file_name)[0] # Default to name without ext
            if matches:
                split_index = matches[-1].start()
                base_name_for_search = current_file_name[:split_index]
            print(f"Base name for Frame.io search: {base_name_for_search}")

            asset_info = find_frame_io_asset_by_name(self.client, project_id, base_name_for_search, self.team_id, self.account_id, asset_type='file', SCRIPT_NAME=SCRIPT_NAME)

            existing_asset_id, asset_type, existing_asset_parent_id = None, None, None
            if asset_info:
                 asset_type = asset_info.get('type')
                 existing_asset_id = asset_info.get('id')
                 existing_asset_parent_id = asset_info.get('parent_id')

            if existing_asset_id:
                if asset_type == 'file':
                    print(f"Found existing file: {existing_asset_id}. Uploading as new version.")
                    newly_uploaded_asset_info = self.client.assets.upload(existing_asset_parent_id, filename_full_path)
                    if newly_uploaded_asset_info and 'id' in newly_uploaded_asset_info:
                        add_version_to_asset(self.client, existing_asset_id, newly_uploaded_asset_info['id'], SCRIPT_NAME)
                elif asset_type == 'version_stack':
                    print(f"Found version stack: {existing_asset_id}. Uploading to stack.")
                    self.client.assets.upload(existing_asset_id, filename_full_path)
                else:
                    print(f"Warning: Asset {existing_asset_id} is type '{asset_type}'. Uploading to CONFORMS folder.")
                    existing_asset_id = None

            if not existing_asset_id:
                print(f"No match for '{base_name_for_search}'. Uploading to 'CONFORMS' folder.")
                target_conforms_folder_id = self.new_folder_id
                if not target_conforms_folder_id:
                    print("CONFORMS folder ID not set. Finding/creating 'CONFORMS' folder.")
                    conforms_asset = find_frame_io_asset_by_name(self.client, project_id, "CONFORMS", self.team_id, self.account_id, asset_type='folder', SCRIPT_NAME=SCRIPT_NAME)
                    if conforms_asset:
                        target_conforms_folder_id = conforms_asset['id']
                    else:
                        created_folder_data = create_frame_io_folder(self.client, self.root_asset_id, "CONFORMS", SCRIPT_NAME)
                        if created_folder_data:
                            target_conforms_folder_id = created_folder_data['id']
                        else:
                             flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to get 'CONFORMS' folder for {current_file_name}. Skipping.", type="error")
                             if progress_window_instance: progress_window_instance.set_text(f"ERROR: No CONFORMS folder for {current_file_name}")
                             continue
                if target_conforms_folder_id:
                    print(f"Uploading '{current_file_name}' to CONFORMS folder (ID: {target_conforms_folder_id}).")
                    self.client.assets.upload(target_conforms_folder_id, filename_full_path)

        if progress_window_instance:
            progress_window_instance.set_text(f'All {files_uploaded_count} file(s) processed.')
            progress_window_instance.set_progress_value(files_uploaded_count)
            progress_window_instance.enable_done_button(True)

        print(f'\n{">" * 10} {SCRIPT_NAME} {VERSION} End {"<" * 10}\n')
    
    @frame_io_api_exception_handler
    def version_upper(self,selection): 
        print(f"Checking Frame.io for existing versions to perform version-up in Flame...")
        self.project_nickname = flame.projects.current_project.nickname # Ensure this is current

        project_details = get_frame_io_project_details(self.client, self.project_nickname, self.team_id, SCRIPT_NAME)
        if not project_details:
            print(f"Frame.io project '{self.project_nickname}' not found. Cannot perform Frame.io based version-up check.")
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Info", f"Frame.io project '{self.project_nickname}' not found. Version-up check against Frame.io will be skipped.", type="info")
            return

        project_id = project_details['project_id']
        print(f"Operating in Frame.io project: {self.project_nickname} (ID: {project_id}) for version-up checks.")

        for item in selection:
            if not isinstance(item, flame.PyClip):
                print(f"Item '{getattr(item, 'name', 'Unknown type')}' is not a PyClip. Skipping.")
                continue

            clip_name_original = str(item.name)
            clip_name_for_search = clip_name_original.strip("'")

            print(f"Checking Frame.io for asset matching Flame clip name: '{clip_name_for_search}'")
            asset_info = find_frame_io_asset_by_name(self.client, project_id, clip_name_for_search, self.team_id, self.account_id, asset_type='file', SCRIPT_NAME=SCRIPT_NAME)

            if asset_info and asset_info.get('id'):
                print(f"Found matching asset '{clip_name_for_search}' (ID: {asset_info['id']}) on Frame.io. Attempting to version up in Flame.")
                matches = list(re.finditer(r'(_[vV])(\d+)', clip_name_for_search))
                if matches:
                    last_match = matches[-1]
                    prefix = last_match.group(1)
                    version_number_str = last_match.group(2)
                    padding = len(version_number_str)
                    next_version_number = int(version_number_str) + 1
                    new_version_digits = f"{next_version_number:0{padding}d}"

                    start_index = last_match.start()
                    end_index = last_match.end()
                    new_clip_name = clip_name_for_search[:start_index] + prefix + new_version_digits + clip_name_for_search[end_index:]

                    item.name = new_clip_name
                    print(f"Successfully versioned up Flame clip: '{clip_name_for_search}' to '{new_clip_name}'")
                else:
                    message = f"Clip '{clip_name_for_search}' found on Frame.io, but name lacks version pattern (e.g., '_v01'). Version-up skipped."
                    print(message)
                    flame.messages.show_in_console(message, type="info", duration=5)
            else:
                print(f"No asset matching '{clip_name_for_search}' found on Frame.io. No version-up for this item.")

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
            "order": 3,
            'actions': [
                {
                    'name': 'Conform Uploader',
                    'order': 0,
                    'separator': 'below',
                    'isVisible': scope_clip,
                    'execute': frame_io_uploader,
                    'minimumVersion': '2024.2'
                }
            ]
        }
    ]
