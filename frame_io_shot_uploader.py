'''
Script Name: frame_io_shot_uploader
Script Version: 0.9.3
Flame Version: 2024.2
Written by: John Geehreng
Creation Date: 01.03.23
Update Date: 12.18.24

Custom Action Type: Media Panel

Description:

    This script will export h264 .mp4's to a FROM_FLAME folder in your job folder, save it to a FROM_FLAME shared library, and upload them to FrameIO.
    It will also automatically create or add to version stacks if it can find a matching base name.
    Script assumes a verion of _v## or _V### in order to match file names.

Updates:
12.18.24 - v0.9.3 - Removed Chelsea and added Catch Exception to help debug. Started using SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
03.20.24 - v0.9.2 - API Updates and Updates for failing searches
12.04.23 - v0.9.1 - Updates for PySide6 (Flame 2025)
09.21.23 - v0.6 - Updated Preset to export mp4's directly from Flame instead of exporting h264 mov's and changing the extension.
04.27.23 - v0.5 - Added Mitch Gardiner and removed Marcus Wei
01.13.23 - v0.31 - changed os.mkdir to subprocess mkdir -p because John was having issues on nyc-lfx-001. Added messages if it can't make a directory.
01.10.23 - v0.3 - fixed issue where search was finding deleted files.
01.05.23 - v0.2 - Added ability to make directories and added scope for clips. Changed pattern to include a user nickname when searching for a match - helps if shot changes artists.

To install:

    Copy script into /opt/Autodesk/shared/python/frame_io


'''

import xml.etree.ElementTree as ET
import flame
import datetime
import os
import subprocess
import re
import glob
import traceback # Keep traceback for general exception handling
from frameioclient import FrameioClient, errors as frameio_errors

SCRIPT_NAME = 'FrameIO Shot Uploader'
SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
VERSION = 'v0.9.3'

#-------------------------------------#
# Main Script

class frame_io_uploader(object):

    def __init__(self, selection):

        print('\n')
        print('>' * 10, f'{SCRIPT_NAME} {VERSION}', ' Start ', '<' * 10, '\n')

        # Paths

        self.config_path = os.path.join(SCRIPT_PATH, 'config') # Good, already using os.path.join
        self.config_xml = os.path.join(self.config_path, 'config.xml') # Good

        # Load config file
        if not self.config(): # Check if config loading was successful
            # If config() returns False (or None and evaluates to False), stop initialization
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", "Failed to load or create configuration. Please check permissions or config file.", type="error")
            # Optionally, could raise an exception here to halt execution if that's preferred.
            return

        # Execution start here:
        self.export_mp4(selection)
        self.upload_to_frameio()

    def config(self):
        """Loads or creates the configuration file.
        Returns True if successful, False otherwise."""

        def get_config_values():
            try:
                xml_tree = ET.parse(self.config_xml)
            except FileNotFoundError:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", f"Config file not found: {self.config_xml}", type="error")
                return False # Indicate failure
            except ET.ParseError:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", f"Error parsing config file: {self.config_xml}. Check its format.", type="error")
                return False # Indicate failure

            root = xml_tree.getroot()

            root = xml_tree.getroot()
            settings_el = root.find('frame_io_settings')
            if settings_el is None:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", f"Invalid config format: <frame_io_settings> not found in {self.config_xml}", type="error")
                return False # Indicate failure

            self.token = settings_el.findtext('token')
            self.account_id = settings_el.findtext('account_id')
            self.team_id = settings_el.findtext('team_id')
            self.jobs_folder = settings_el.findtext('jobs_folder')
            self.preset_path_h264 = settings_el.findtext('preset_path_h264')

            if not all([self.token, self.account_id, self.team_id, self.jobs_folder, self.preset_path_h264]):
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", "One or more settings are missing from the config file. Please check config.xml.", type="error")
                return False # Indicate failure

            # Basic check for placeholder token
            if 'fio-x-xxxxxx' in self.token:
                 flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Warning", f"The token in {self.config_xml} appears to be a placeholder. Please update it with your actual Frame.io API token.", type="warning")
                 # We can still return True here, as the script might work for some read-only operations or if the user updates it soon.

            print(f"{SCRIPT_NAME}: Config loaded successfully.")
            return True # Indicate success
        

        def create_config_file():
            """Creates the config directory and a default config file.
            Returns True if config file exists or is created (but may need user input), False on error."""
            if not os.path.isdir(self.config_path):
                try:
                    os.makedirs(self.config_path, exist_ok=True)
                    print(f"Config directory created: {self.config_path}")
                except OSError as e:
                    flame.messages.show_in_dialog(
                        title=f"{SCRIPT_NAME}: Error",
                        message=f"Unable to create config folder: {self.config_path}\nError: {e}\nCheck folder permissions.",
                        type="error")
                    return False

            if not os.path.isfile(self.config_xml):
                print(f"{SCRIPT_NAME}: Config file does not exist. Creating new config file: {self.config_xml}")
                # Use os.path.join for default preset path for better platform compatibility
                default_preset_path = os.path.join(SCRIPT_PATH, "presets", "UC H264 10Mbits.xml")
                # Using triple quotes for cleaner multiline string and ensuring it's an f-string
                config_content = f"""<settings>
    <frame_io_settings>
        <token>fio-x-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx-xxxxxxxxxxx-xxxxxxxxxxx</token>
        <account_id>xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx</account_id>
        <team_id>xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx</team_id>
        <jobs_folder>/Volumes/vfx/UC_Jobs</jobs_folder>
        <preset_path_h264>{default_preset_path}</preset_path_h264>
    </frame_io_settings>
</settings>
"""
                try:
                    with open(self.config_xml, 'w') as config_file:
                        config_file.write(config_content.strip()) # Ensure .strip() is used
                    print(f"Default config file created: {self.config_xml}")
                    flame.messages.show_in_dialog(
                        title=f"{SCRIPT_NAME}: Config File Created", # More specific title
                        message=f"A new config file was created at:\n{self.config_xml}\nPlease update it with your Frame.io credentials and verify paths.",
                        type="info"
                        )
                    return True # File created/exists, though may need user edits
                except IOError as e:
                    flame.messages.show_in_dialog(
                        title=f"{SCRIPT_NAME}: File Creation Error",
                        message=f"Unable to create config file: {self.config_xml}\nError: {e}\nCheck file permissions.",
                        type="error")
                    return False
            return True

        if not os.path.isfile(self.config_xml):
            if not create_config_file():
                return False

        return get_config_values()
    
    def catch_exception(method):
        def wrapper(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except frameio_errors.APIError as e:
                error_message = f"Frame.io API Error in {method.__name__}:\n{e}\nURL: {e.response.url if e.response else 'N/A'}\nStatus: {e.response.status_code if e.response else 'N/A'}"
                print(error_message)
                traceback.print_exc()
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Frame.io API Error", error_message, type="error")
            # If requests is still potentially used by the SDK indirectly or other parts of the code.
            # except requests.exceptions.RequestException as e:
            #     error_message = f"Network Error in {method.__name__}: {e}"
            #     print(error_message)
            #     traceback.print_exc()
            #     flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Network Error", error_message, type="error")
            except Exception as e:
                error_message = f"An unexpected error occurred in {method.__name__}:\n{e}"
                print(error_message)
                traceback.print_exc()
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Unexpected Error", error_message, type="error")
        return wrapper
    
    @catch_exception
    def export_mp4(self, selection):
        self.project_nickname = flame.projects.current_project.nickname
        self.project_name = flame.projects.current_project.name

        dateandtime = datetime.datetime.now()
        today = (dateandtime.strftime("%Y-%m-%d"))
        time = (dateandtime.strftime("%H%M"))

        # Define Export Path & Check for Preset
        if not self.preset_path_h264 or not os.path.isfile(self.preset_path_h264): # Check if path is not None/empty and file exists
            error_msg = f"Cannot find Export Preset: {self.preset_path_h264 or 'Path not configured'}"
            print(error_msg)
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", error_msg, type="error")
            return # Stop execution

        print(f"Export Preset Found: {self.preset_path_h264}")

        # Use os.path.join for export_dir and ensure all parts are strings
        self.export_dir = os.path.join(
            str(self.jobs_folder),
            str(self.project_nickname),
            "FROM_FLAME",
            str(today),
            str(time)
        )
        print(f"Target export directory: {self.export_dir}")

        if not os.path.isdir(self.export_dir):
            print(f"Export directory '{self.export_dir}' doesn't exist. Creating it now.")
            try:
                os.makedirs(self.export_dir, exist_ok=True)
                print(f"Successfully created directory: {self.export_dir}")
            except OSError as e:
                message = f"Could not create directory: {self.export_dir}\nError: {e}"
                print(message)
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Directory Creation Error", message, type="error")
                return # Stop execution

        #Define Exporter
        exporter = flame.PyExporter()
        exporter.foreground = True
        exporter.export_between_marks = False
        exporter.use_top_video_track = True

        for item in selection:
            exporter.export(item, self.preset_path_h264, self.export_dir)
    
    @catch_exception
    def upload_to_frameio(self):
        print("Starting FrameIO stuff...")     

        # Initialize the client library using the token from config
        client = FrameioClient(self.token)

        print(f"Processing for Flame project: {self.project_nickname}")

        # Get existing project or create a new one
        root_asset_id, project_id = self.get_fio_projects() # This now returns (None, None) if not found

        if not project_id: # If project doesn't exist
            print(f"Frame.io project '{self.project_nickname}' not found. Attempting to create it.")
            # create_fio_project will internally set self.new_folder_id for "SHOTS"
            root_asset_id, project_id = self.create_fio_project(self.project_nickname)
            if not project_id: # If creation also failed
                flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Could not find or create Frame.io project: {self.project_nickname}. Halting upload.", type="error")
                return # Stop execution

        print(f"Using Frame.io Project ID: {project_id}, Root Asset ID: {root_asset_id}")
        self.root_asset_id = root_asset_id # Ensure self.root_asset_id is set for use in folder creation if needed

        # Construct search pattern for exported files
        # Using os.path.join for robustness, and glob pattern for all files in the directory
        self.export_path_glob = os.path.join(self.export_dir, '*') # Simpler glob for files directly in export_dir
        files_to_upload = glob.glob(self.export_path_glob)

        if not files_to_upload:
            print(f"No files found in {self.export_dir} to upload.")
            flame.messages.show_in_dialog(f"{SCRIPT_NAME}", f"No files found in the export directory: {self.export_dir}", type="info")
            return

        for filename_full_path in files_to_upload:
            if os.path.isdir(filename_full_path): # Skip directories if glob picks them up
                continue

            print('\n') # Newline for readability per file
            _path, file_name_only = os.path.split(filename_full_path) # Use clearer variable names
            print(f"Processing file: {filename_full_path}")
            print(f"File name: {file_name_only}")

            # Extract base name for searching (e.g., "SHOT_010" from "SHOT_010_artist_v01.mp4")
            # This pattern assumes versioning like _v01 or _V001 and optional artist initials
            pattern = r'_[a-zA-Z]*?_[vV]\d+' # Made artist part non-greedy
            base_name_for_search = re.split(pattern, file_name_only)[0]
            print(f"Base name for Frame.io search: {base_name_for_search}")

            # Find a matching asset in Frame.io
            # find_a_fio_asset now returns (type, id, parent_id) or (None, None, None)
            asset_type, existing_asset_id, existing_asset_parent_id = self.find_a_fio_asset(project_id, base_name_for_search)

            if existing_asset_id: # If a matching asset is found
                if asset_type == 'file':
                    print(f"Found existing file asset: {existing_asset_id}. Uploading as new version.")
                    # Upload the new file to the parent of the existing asset, then version it.
                    # This assumes the Frame.io SDK's upload returns info including the new asset's ID.
                    newly_uploaded_asset_info = client.assets.upload(existing_asset_parent_id, filename_full_path)
                    if newly_uploaded_asset_info and 'id' in newly_uploaded_asset_info:
                        self.version_asset(existing_asset_id, newly_uploaded_asset_info['id'])
                    else:
                        print(f"Error: Failed to upload new version for {file_name_only}. Upload response: {newly_uploaded_asset_info}")
                        flame.messages.show_in_dialog(f"{SCRIPT_NAME} Upload Error", f"Failed to upload new version for {file_name_only}.", type="error")

                elif asset_type == 'version_stack':
                    print(f"Found existing version stack: {existing_asset_id}. Adding file as a new version to this stack.")
                    # Upload directly to the version stack ID.
                    client.assets.upload(existing_asset_id, filename_full_path)

                else: # Should not happen if find_a_fio_asset returns correctly
                    print(f"Warning: Found asset {existing_asset_id} but it's of unexpected type '{asset_type}'. Attempting to upload to SHOTS folder.")
                    # Fallback to uploading to SHOTS folder (logic below)
                    existing_asset_id = None # Force fallback

            if not existing_asset_id: # If no match found, or if fallback from unexpected type
                print(f"No existing match found for '{base_name_for_search}'. Uploading as new asset to 'SHOTS' folder.")

                # self.new_folder_id should ideally be the 'SHOTS' folder ID set during project creation/retrieval.
                # However, we double check and try to find/create it if necessary.
                target_shots_folder_id = self.new_folder_id

                # Validate if self.new_folder_id is indeed the SHOTS folder or if it needs to be (re)found.
                # This check is a bit simplistic; a more robust way would be to store folder names with IDs.
                # For now, if create_fio_project was called, new_folder_id is the SHOTS folder from that run.
                # If get_fio_projects was called, new_folder_id might not be specifically SHOTS.

                if not target_shots_folder_id: # If new_folder_id is not set (e.g. project existed)
                    print("self.new_folder_id not set to SHOTS folder, attempting to find or create SHOTS folder.")
                    target_shots_folder_id = self.find_shots_folder(project_id) # Attempt to find it
                    if not target_shots_folder_id: # Still not found
                        print("'SHOTS' folder not found. Creating it now.")
                        # self.create_fio_folder updates self.new_folder_id with the new folder's ID
                        target_shots_folder_id = self.create_fio_folder(self.root_asset_id, "SHOTS")
                        if not target_shots_folder_id:
                             flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to find or create 'SHOTS' folder in project {self.project_nickname}. Skipping upload for {file_name_only}.", type="error")
                             continue # Skip this file

                print(f"Uploading '{file_name_only}' to 'SHOTS' folder (ID: {target_shots_folder_id}).")
                client.assets.upload(target_shots_folder_id, filename_full_path)

        # Standardized to f-string
        print(f"\n{'>' * 10} {SCRIPT_NAME} {VERSION} End {'<' * 10}\n")

    @catch_exception
    def create_fio_project(self, flame_project_name:str):
        """Creates a new Frame.io project and default folders ('CONFORMS', 'SHOTS').
        Sets self.new_folder_id to the ID of the created 'SHOTS' folder."""
        print(f"Attempting to create Frame.io project: {flame_project_name}")
        client = FrameioClient(self.token)
        try:
            project_data = client.projects.create(
                team_id=self.team_id,
                name=flame_project_name,
                private=False # Consider making this configurable or based on project settings
            )
        except frameio_errors.APIError as e:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to create project '{flame_project_name}'. API Error: {e}", type="error")
            return None, None

        root_asset_id = project_data['root_asset_id']
        project_id = project_data['id']
        print(f"Project '{flame_project_name}' created successfully. Project ID: {project_id}, Root Asset ID: {root_asset_id}")

        # Create default folders within the new project
        self.create_fio_folder(root_asset_id, "CONFORMS") # self.new_folder_id will be updated by this
        # Crucially, the 'SHOTS' folder ID is needed by upload_to_frameio if uploading new assets.
        # self.create_fio_folder will update self.new_folder_id with the ID of the folder it creates.
        # So, after the next line, self.new_folder_id will be the ID of "SHOTS".
        shots_folder_id = self.create_fio_folder(root_asset_id, "SHOTS")
        if shots_folder_id:
             print(f"'SHOTS' folder created with ID: {shots_folder_id}. self.new_folder_id is now {self.new_folder_id}")
        else:
            print(f"Warning: Failed to create 'SHOTS' folder for new project '{flame_project_name}'.")
            # self.new_folder_id would retain the ID from "CONFORMS" or be None if that also failed.
            # This state should be handled by the caller or upload_to_frameio.

        return root_asset_id, project_id
    
    @catch_exception
    def create_fio_folder(self, parent_asset_id: str, name: str):
        """Creates a folder under the given parent_asset_id.
        Updates self.new_folder_id with the ID of the created folder.
        Returns the ID of the created folder, or None on failure."""
        print(f"Creating folder '{name}' under parent asset ID: {parent_asset_id}")
        client = FrameioClient(self.token)
        try:
            folder_data = client.assets.create(
                parent_asset_id=parent_asset_id,
                name=name,
                type="folder"
            )
            self.new_folder_id = folder_data['id'] # Update self.new_folder_id
            print(f"Folder '{name}' created successfully with ID: {self.new_folder_id}")
            return self.new_folder_id
        except frameio_errors.APIError as e:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to create folder '{name}' under {parent_asset_id}. API Error: {e}", type="error")
            # Ensure self.new_folder_id is not inadvertently left with an old ID if this was the SHOTS folder creation
            if name == "SHOTS":
                self.new_folder_id = None # Explicitly clear if SHOTS folder failed
            return None

    @catch_exception
    def version_asset(self, original_asset_id: str, new_asset_id: str):
        """Adds new_asset_id as a new version to original_asset_id."""
        print(f"Creating new version for asset {original_asset_id} using uploaded asset {new_asset_id}")
        client = FrameioClient(self.token)
        try:
            client.assets.add_version(original_asset_id, new_asset_id)
            print(f"Successfully versioned asset {original_asset_id} with {new_asset_id}.")
        except frameio_errors.APIError as e:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to version asset {original_asset_id}. API Error: {e}", type="error")

    def get_fio_projects(self):
        """Retrieves a specific Frame.io project by its nickname from the configured team.
        Also attempts to find and set self.new_folder_id to the 'SHOTS' folder ID if project is found.
        Returns (root_asset_id, project_id) or (None, None) if not found or error."""
        print(f"Searching for Frame.io project named '{self.project_nickname}' in team ID '{self.team_id}'.")
        client = FrameioClient(self.token)
        try:
            projects_iterator = client.teams.list_projects(self.team_id) # This returns an iterator
            for project in projects_iterator:
                # Ensure checks for archived or deleted are appropriate for your SDK version
                # The attributes might be 'is_archived' or similar, and presence of 'deleted_at'.
                if project['name'] == self.project_nickname and not project.get('archived') and not project.get('deleted_at'):
                    print(f"Found project: {project['name']} (ID: {project['id']})")
                    # If project is found, try to find its 'SHOTS' folder and set self.new_folder_id
                    shots_folder_id = self.find_shots_folder(project['id'])
                    if shots_folder_id:
                        self.new_folder_id = shots_folder_id
                        print(f"'SHOTS' folder found with ID: {self.new_folder_id}")
                    else:
                        # Clarified warning message
                        print(f"Warning: 'SHOTS' folder not found in existing project '{project['name']}'. This is okay if not uploading new files to 'SHOTS'. It can be created if needed.")
                        self.new_folder_id = None
                    return project['root_asset_id'], project['id']
        except frameio_errors.APIError as e:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to list projects for team {self.team_id}. API Error: {e}", type="error")
            return None, None # Return None on error

        print(f"Project '{self.project_nickname}' not found in team '{self.team_id}'. This is not an error; project will be created if needed.")
        return None, None
    
    @catch_exception
    def find_a_fio_asset(self, project_id: str, base_name: str):
        """Finds an asset (file or version_stack) by its base name within a given project.
        Returns (type, id, parent_id) or (None, None, None) if not found."""
        print(f"Searching for asset with base name '{base_name}' in project ID: {project_id}")
        client = FrameioClient(self.token)
        try:
            # Assuming client.search.library() is the correct method.
            # The SDK documentation should clarify pagination, filtering by type, etc.
            # For this example, we iterate and filter manually if direct type filtering isn't available or robust.
            search_results = client.search.library(
                account_id=self.account_id,
                project_id=project_id,
                query=base_name
                # Consider adding type='file,version_stack' if supported by the SDK search query
            )

            for item in search_results: # search_results might be a list or an iterator
                # Check if the item name starts with base_name to be more precise than just 'in'
                # This helps differentiate "SHOT_010" from "EXTRA_SHOT_010" if base_name is "SHOT_010"
                if item['name'].startswith(base_name) and (item['type'] == 'file' or item['type'] == 'version_stack'):
                    print(f"Found matching asset: {item['name']} (Type: {item['type']}, ID: {item['id']})")
                    return item['type'], item['id'], item.get('parent_id') # Use .get for parent_id as it might not always be present
        except frameio_errors.APIError as e:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to search for asset '{base_name}'. API Error: {e}", type="error")
            return None, None, None

        print(f"No matching asset found for '{base_name}' in project {project_id}.")
        return None, None, None

    @catch_exception
    def find_shots_folder(self, project_id: str):
        """Finds the 'SHOTS' folder within a given project.
        Returns folder_id or None if not found."""
        print(f"Searching for 'SHOTS' folder in project ID: {project_id}")
        client = FrameioClient(self.token)
        try:
            search_results = client.search.library(
                account_id=self.account_id,
                project_id=project_id,
                query="SHOTS",
                # type="folder" # Specify type if the SDK supports it in the query
            )
            for item in search_results:
                if item['type'] == 'folder' and item['name'].upper() == "SHOTS": # Case-insensitive check for "SHOTS"
                    print(f"Found 'SHOTS' folder with ID: {item['id']}")
                    return item['id']
        except frameio_errors.APIError as e:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to search for 'SHOTS' folder. API Error: {e}", type="error")
            return None
        
        print(f"'SHOTS' folder not found in project {project_id}.")
        return None

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
