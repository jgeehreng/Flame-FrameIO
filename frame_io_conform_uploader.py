'''
Script Name: frame_io_conform_uploader
Script Version: 1.2
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
12.18.24 - v1.2   Removed Chelsea and added Catch Exception to help debug. Started using SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
09.28.24 - v1.1.2 Simplified the way of searching for the FROM_FLAME shared library and it's subfolders.
09.24.24 - v1.0.2 Adjusted base name search to work with v## or V##. Splits at the last match.
09.19.24 - v1.0.1 Fixed a bug where script would fail if there wasn't an existing project
09.13.24 - v1.0 - Added automatic version upper
06.13.24 - v0.9.3 - Added Progress window for uploads
03.20.24 - v0.9.2 - API Updates and Updates for failing searches
12.04.23 - v0.8 - Updates for PySide6 (Flame 2025)
10.31.23 - v0.7 - Minor print Adjustments
09.21.23 - v0.6 - Updated Preset to export mp4's directly from Flame instead of exporting h264 mov's and changing the extension.
04.27.23 - v0.5 - Added Mitch Gardiner and removed Marcus Wei
01.11.23 - v04.1- changed pattern from: r'_[vV]\d*' to r'_[vV]\d+'
01.10.23 - v0.4 - fixed issue where search was finding deleted files.
01.05.23 - v0.3 - added scope

To install:

    Copy script into /opt/Autodesk/shared/python/frame_io
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
import traceback # Ensure traceback is imported for catch_exception
from frameioclient import FrameioClient, errors as frameio_errors
from pyflame_lib_frame_io import PyFlameProgressWindow

SCRIPT_NAME = 'FrameIO Conform Uploader'
SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
VERSION = 'v1.2'

#-------------------------------------#
# Main Script

class frame_io_uploader(object):

    def __init__(self, selection):

        print('\n')
        print('>' * 10, f'{SCRIPT_NAME} {VERSION}', ' Start ', '<' * 10, '\n')

        # Paths

        self.config_path = os.path.join(SCRIPT_PATH, 'config')
        self.config_xml = os.path.join(self.config_path, 'config.xml')

        # Load config file
        # self.config() returns False if loading/creation fails or needs user intervention.
        if not self.config():
            print(f"{SCRIPT_NAME} {VERSION}: Configuration failed. Exiting.")
            # No flame.message here as self.config() should have already shown one.
            return # Stop initialization

        # Search for existing version - if a matching version (with the same exact name) is found the selection will be automatically versioned up before being exported.
        self.version_upper(selection)

        # Copy to the FROM_FLAME shared library and export
        # Check if export_path was successfully set; if not, critical failure.
        if not hasattr(self, 'export_path') or not self.export_path:
            print(f"{SCRIPT_NAME} {VERSION}: Export path not set after export_and_copy_path. Halting.")
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", "Export path was not set. Cannot proceed with upload.", type="error")
            return

        # Upload to FrameIO. Find appropriate folder and version stack if a match is found.
        self.upload_to_frameio()

    def catch_exception(method):
        def wrapper(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except frameio_errors.APIError as e:
                error_message = f"Frame.io API Error in {method.__name__}:\n{e}\nURL: {e.response.url if e.response else 'N/A'}\nStatus: {e.response.status_code if e.response else 'N/A'}"
                print(error_message)
                traceback.print_exc()
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Frame.io API Error", error_message, type="error")
            except Exception as e:
                error_message = f"An unexpected error occurred in {method.__name__}:\n{e}"
                print(error_message)
                traceback.print_exc()
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Unexpected Error", error_message, type="error")
        return wrapper
    
    def config(self):
        """Loads or creates the configuration file.
        Returns True if successful, False otherwise."""

        def get_config_values():

            xml_tree = ET.parse(self.config_xml)
            root = xml_tree.getroot()

            try:
                xml_tree = ET.parse(self.config_xml)
            except FileNotFoundError:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", f"Config file not found: {self.config_xml}", type="error")
                return False
            except ET.ParseError:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", f"Error parsing config file: {self.config_xml}. Check its format.", type="error")
                return False

            root = xml_tree.getroot()
            settings_el = root.find('frame_io_settings')
            if settings_el is None:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", f"Invalid config format: <frame_io_settings> not found in {self.config_xml}", type="error")
                return False

            self.token = settings_el.findtext('token')
            self.account_id = settings_el.findtext('account_id')
            self.team_id = settings_el.findtext('team_id')
            self.jobs_folder = settings_el.findtext('jobs_folder')
            self.preset_path_h264 = settings_el.findtext('preset_path_h264')

            if not all([self.token, self.account_id, self.team_id, self.jobs_folder, self.preset_path_h264]):
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", "One or more settings are missing from the config file. Please check config.xml.", type="error")
                return False

            if 'fio-x-xxxxxx' in self.token:
                 flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Warning", f"The token in {self.config_xml} appears to be a placeholder. Please update it with your actual Frame.io API token.", type="warning")

            print(f"{SCRIPT_NAME}: Config loaded successfully.")
            return True

        def create_config_file():
            """Creates the config directory and a default config file.
            Returns True if config file exists/is created (may need user input), False on error."""
            if not os.path.isdir(self.config_path):
                try:
                    os.makedirs(self.config_path, exist_ok=True)
                    print(f"Config directory created: {self.config_path}")
                except OSError as e:
                    flame.messages.show_in_dialog(
                        title=f"{SCRIPT_NAME}: Directory Creation Error",
                        message=f"Unable to create config folder: {self.config_path}\nError: {e}\nCheck folder permissions.",
                        type="error")
                    return False

            if not os.path.isfile(self.config_xml):
                print(f"{SCRIPT_NAME}: Config file does not exist. Creating new config file: {self.config_xml}")
                default_preset_path = os.path.join(SCRIPT_PATH, "presets", "UC H264 10Mbits.xml")
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
                        config_file.write(config_content.strip())
                    print(f"Default config file created: {self.config_xml}")
                    flame.messages.show_in_dialog(
                        title=f"{SCRIPT_NAME}: Config File Created",
                        message=f"A new config file was created at:\n{self.config_xml}\nPlease update it with your Frame.io credentials and verify paths.",
                        type="info")
                    return True
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

        return get_config_values() # Returns True if values loaded, False otherwise
    
    @catch_exception
    def export_and_copy_path(self, selection):

        # self.project_nickname = flame.projects.current_project.nickname
        dateandtime = datetime.datetime.now()
        today = (dateandtime.strftime("%Y-%m-%d"))
        time = (dateandtime.strftime("%H%M"))
        shared_libs = flame.projects.current_project.shared_libraries
        
        #Check for FROM_FLAME Shared Library if missing create one
        sharedlib = None
        # Look for a shared library called "FROM_FLAME"
        for libary in shared_libs:      
            if libary.name == "FROM_FLAME":
                sharedlib = libary
        # If it's found, keep going. Otherwise create a shared library called "FROM FLAME"
        if sharedlib:
            pass
        else:
            sharedlib = flame.projects.current_project.create_shared_library('FROM_FLAME')

        #Define Export Path & Check for Preset

        preset_check = (str(os.path.isfile(self.preset_path_h264)))

        if preset_check == 'True':
            pass
            # print ("Export Preset Found")
        else:
            # print ('Export Preset Not Found.')
            flame.messages.show_in_dialog(
                title=f"{SCRIPT_NAME} Error",
                message=f"Cannot find Export Preset at path: {self.preset_path_h264}",
                type="error")
            return

        # Use os.path.join for all path constructions for better platform compatibility
        export_base_dir = os.path.join(str(self.jobs_folder), str(self.project_nickname), "FROM_FLAME")
        export_dir_with_date = os.path.join(export_base_dir, str(today))

        # Create directories if they don't exist
        try:
            if not os.path.isdir(export_dir_with_date): # Check before creating
                os.makedirs(export_dir_with_date, exist_ok=True)
                print(f"Created export directory: {export_dir_with_date}")
        except OSError as e:
            flame.messages.show_in_dialog(
                title=f"{SCRIPT_NAME} Error",
                message=f"Could not create export directory: {export_dir_with_date}\nError: {e}",
                type="error")
            return

        #Define Exporter
        exporter = flame.PyExporter()
        exporter.foreground = True
        exporter.export_between_marks = True
        exporter.use_top_video_track = True

        # Look for a Folder with Today's Date
        todays_match=False
        for folder in sharedlib.folders:
            if folder.name == today:
                todays_match = True
            # print ("Today's Folder # is: ", today_folder_number)
        
        # If it finds a match, create a timestamped folder
        if todays_match == True:
            sharedlib.acquire_exclusive_access()
            postingfolder = folder.create_folder(time)
            tab = flame.get_current_tab()
            if tab == 'MediaHub':
                flame.set_current_tab("Timeline")
            for item in selection:
                flame.media_panel.copy(item, postingfolder)
            # Use export_dir_with_date for the export operation
            exporter.export(postingfolder, self.preset_path_h264, export_dir_with_date)
            
            # Collapse everything
            if sharedlib.exclusive_access(): # Check before trying to release
                sharedlib.expanded = False # Best effort
                if hasattr(postingfolder, 'expanded'): postingfolder.expanded = False
                # Ensure 'folder' is the correct variable for the parent (today's date folder)
                # and check its existence before trying to collapse.
                # 'folder' variable was from the loop: for folder in sharedlib.folders:
                # It might not be what's intended here if todays_match was True.
                # If todays_match was True, 'folder' is the existing date folder.
                if 'folder' in locals() and hasattr(folder, 'expanded'):
                    folder.expanded = False
                sharedlib.release_exclusive_access()

            posted_folder_name_cleaned = str(postingfolder.name).strip("'")
            self.export_path = os.path.join(export_dir_with_date, posted_folder_name_cleaned)

            print(f"Exported to: {self.export_path}")
            qt_app_instance = QtWidgets.QApplication.instance()
            if qt_app_instance:
                qt_app_instance.clipboard().setText(self.export_path)
            else:
                print("Warning: QApplication instance not found. Could not copy export path to clipboard.")

        else: # todays_match == False
            print(f"Today's date folder '{today}' not found in 'FROM_FLAME' shared library. Creating it.")
            sharedlib.acquire_exclusive_access()
            try:
                today_folder = sharedlib.create_folder(today)
                postingfolder = today_folder.create_folder(time)

                tab = flame.get_current_tab()
                if tab == 'MediaHub':
                    flame.set_current_tab("Timeline")

                for item in selection:
                    flame.media_panel.copy(item, postingfolder)

                # Export to the directory named after the date.
                exporter.export(postingfolder, self.preset_path_h264, export_dir_with_date)

                # Collapse everything
                sharedlib.expanded = False # Best effort
                if hasattr(postingfolder, 'expanded'): postingfolder.expanded = False
                if hasattr(postingfolder, 'parent') and hasattr(postingfolder.parent, 'expanded'):
                    postingfolder.parent.expanded = False

            except Exception as e:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Error during shared library operations or export: {e}", type="error")
                traceback.print_exc() # Keep for debugging, but user gets dialog
            finally: # Ensure access is always released
                 if sharedlib.exclusive_access():
                    sharedlib.release_exclusive_access()

            if 'postingfolder' in locals() and hasattr(postingfolder, 'name'):
                posted_folder_name_cleaned = str(postingfolder.name).strip("'")
                self.export_path = os.path.join(export_dir_with_date, posted_folder_name_cleaned)
                print(f"Exported to: {self.export_path}")
                qt_app_instance = QtWidgets.QApplication.instance()
                if qt_app_instance:
                    qt_app_instance.clipboard().setText(self.export_path)
                else:
                    print("Warning: QApplication instance not found. Could not copy export path to clipboard.")
            else: # This case implies an error occurred before postingfolder was defined
                print("Error: 'postingfolder' was not defined due to an earlier error. Cannot set export path or copy to clipboard.")
                self.export_path = None # Ensure it's None if export logic failed critically

    @catch_exception
    def upload_to_frameio(self):
        print("Starting FrameIO stuff...")

        # Initialize the client library
        client = FrameioClient(self.token)
        print(f"Frame.io Project Nickname: {self.project_nickname}")

        root_asset_id, project_id = self.get_fio_projects() # This method now also tries to set self.new_folder_id to CONFORMS folder ID
        if not project_id: # Project not found
            print(f"Project '{self.project_nickname}' not found, attempting to create it.")
            # create_fio_project sets self.new_folder_id to the CONFORMS folder ID upon successful creation.
            root_asset_id, project_id = self.create_fio_project(self.project_nickname)
            if not project_id: # Creation failed
                flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Could not find or create Frame.io project: {self.project_nickname}. Upload cancelled.", type="error")
                return
        
        print(f"Using Project ID: {project_id}, Root Asset ID: {root_asset_id}")
        self.root_asset_id = root_asset_id

        # Construct glob pattern using os.path.join for robustness
        # self.export_path should be the directory containing the files, not a glob pattern itself.
        if not hasattr(self, 'export_path') or not self.export_path or not os.path.isdir(self.export_path):
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Export path is not set or is not a valid directory: {getattr(self, 'export_path', 'Not set')}", type="error")
            return

        glob_pattern = os.path.join(self.export_path, '*') # Get all files directly in the export_path
        files_to_upload = glob.glob(glob_pattern)

        # Filter out directories from the glob results, keeping only files
        files_to_upload = [f for f in files_to_upload if os.path.isfile(f)]

        if not files_to_upload:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME}", f"No files found to upload in {self.export_path}.", type="info")
            return

        # Progress Bar Setup
        number_of_files = len(files_to_upload)
        files_uploaded_count = 0
        try:
            self.progress_window = PyFlameProgressWindow(
                num_to_do=number_of_files,
                title='Frame.io Conform Uploading...',
                text=f'Starting upload of {number_of_files} file(s)...',
                enable_done_button=False
            )
        except Exception as e:
            print(f"Error initializing progress window: {e}")
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", "Could not initialize progress window. Upload will continue without progress display.", type="warning")
            self.progress_window = None # Ensure it's None if failed

        print(f"Files to upload: {files_to_upload}")
        for filename_full_path in files_to_upload: # Use a more descriptive variable name
            files_uploaded_count += 1
            current_file_name = os.path.basename(filename_full_path)
            print(f"\nProcessing file {files_uploaded_count}/{number_of_files}: {filename_full_path}")

            if self.progress_window:
                self.progress_window.set_text(f'Uploading: {current_file_name} ({files_uploaded_count} of {number_of_files})')
                self.progress_window.set_progress_value(files_uploaded_count)
            # Check for v## or V## to extract base name for searching
            pattern = r'(_[vV]\d+)' # Group the version part
            # Find all matches of the pattern in the text
            matches = list(re.finditer(pattern, current_file_name))

            if matches:
                # Split at the start of the last version string found
                split_index = matches[-1].start()
                base_name_for_search = current_file_name[:split_index]
            else:    
                # If no version pattern, use the full name (minus extension for cleaner search if preferred)
                base_name_for_search = os.path.splitext(current_file_name)[0]
            print(f"Base name for Frame.io search: {base_name_for_search}")

            # Find an existing asset using project_id and the derived base_name_for_search
            asset_type, existing_asset_id, existing_asset_parent_id = self.find_a_fio_asset(project_id, base_name_for_search)

            if existing_asset_id:
                if asset_type == 'file':
                    print(f"Found existing file asset: {existing_asset_id}. Uploading as new version.")
                    newly_uploaded_asset = client.assets.upload(existing_asset_parent_id, filename_full_path)
                    if newly_uploaded_asset and 'id' in newly_uploaded_asset:
                        self.version_asset(existing_asset_id, newly_uploaded_asset['id'])
                    else:
                        print(f"Error uploading new version for {current_file_name}. Response: {newly_uploaded_asset}")
                        flame.messages.show_in_dialog(f"{SCRIPT_NAME} Upload Error", f"Failed to upload new version for {current_file_name}.",type="error")

                elif asset_type == 'version_stack':
                    print(f"Found version stack with ID: {existing_asset_id}. Uploading to stack.")
                    client.assets.upload(existing_asset_id, filename_full_path)
                else: # Should not happen if find_a_fio_asset is specific enough
                    print(f"Warning: Found asset {existing_asset_id} of unexpected type '{asset_type}'. Uploading to CONFORMS folder as new asset.")
                    existing_asset_id = None # Force fallback to upload as new

            if not existing_asset_id: # If no match, or forced fallback
                print(f"No existing asset match for '{base_name_for_search}'. Uploading as new asset to 'CONFORMS' folder.")

                # self.new_folder_id should be the CONFORMS folder ID,
                # set by get_fio_projects or create_fio_project.
                target_conforms_folder_id = self.new_folder_id

                if not target_conforms_folder_id: # If not set, try to find or create it.
                    print("CONFORMS folder ID not set from project load/create. Attempting to find/create now.")
                    target_conforms_folder_id = self.find_conforms_folder(project_id)
                    if not target_conforms_folder_id:
                        print("'CONFORMS' folder not found. Creating it.")
                        target_conforms_folder_id = self.create_fio_folder(self.root_asset_id, "CONFORMS")
                        if not target_conforms_folder_id: # If creation also fails
                            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to find or create 'CONFORMS' folder. Skipping upload of {current_file_name}.", type="error")
                            if self.progress_window: self.progress_window.set_text(f"ERROR: Failed to get CONFORMS folder for {current_file_name}")
                            continue # Skip this file

                if target_conforms_folder_id:
                    print(f"Uploading '{current_file_name}' to 'CONFORMS' folder (ID: {target_conforms_folder_id}).")
                    client.assets.upload(target_conforms_folder_id, filename_full_path)
                # No else here, failure to get target_conforms_folder_id is handled by 'continue'

        # Finalize Progress Bar
        if self.progress_window:
            self.progress_window.set_text(f'All {files_uploaded_count} file(s) processed.')
            self.progress_window.set_progress_value(files_uploaded_count) # Ensure it's at max
            self.progress_window.enable_done_button(True)
            # User can click "Done" to close the progress window.

        print('>' * 10, f'{SCRIPT_NAME} {VERSION}', ' End ', '<' * 10, '\n')
    
    @catch_exception
    def create_fio_project(self, flame_project_name:str):
        """Creates a Frame.io project and default folders. Sets self.new_folder_id to CONFORMS folder ID."""
        print(f"Creating Frame.io project: {flame_project_name}")
        client = FrameioClient(self.token)
        project_data = client.projects.create(
            team_id=self.team_id,
            name=flame_project_name,
            private=False
        )
        root_asset_id = project_data['root_asset_id']
        project_id = project_data['id']
        print(f"Project '{flame_project_name}' created. Project ID: {project_id}, Root Asset ID: {root_asset_id}")

        # Create default folders. create_fio_folder updates self.new_folder_id.
        self.create_fio_folder(root_asset_id, "SHOTS")
        conforms_id = self.create_fio_folder(root_asset_id, "CONFORMS")
        if conforms_id:
            print(f"'CONFORMS' folder created with ID: {conforms_id}. self.new_folder_id is now {self.new_folder_id}")
        else:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to create 'CONFORMS' folder for new project '{flame_project_name}'. Uploads may fail.", type="error")
            return None, None

        return root_asset_id, project_id

    @catch_exception
    def create_fio_folder(self, parent_asset_id: str, name: str):
        """Creates a folder. Updates self.new_folder_id with the created folder's ID. Returns folder ID."""
        print(f"Creating folder '{name}' under parent asset ID: {parent_asset_id}")
        client = FrameioClient(self.token)
        folder_data = client.assets.create(
            parent_asset_id=parent_asset_id,
            name=name,
            type="folder"
        )
        self.new_folder_id = folder_data['id']
        print(f"Folder '{name}' created with ID: {self.new_folder_id}")
        return self.new_folder_id

    @catch_exception
    def version_asset(self, original_asset_id: str, new_asset_id: str):
        """Versions an asset."""
        print(f"Versioning asset {original_asset_id} with new version {new_asset_id}")
        client = FrameioClient(self.token)
        client.assets.add_version(original_asset_id, new_asset_id)
        print("Asset versioned successfully.")

    @catch_exception
    def get_fio_projects(self):
        """Gets a Frame.io project by nickname. Sets self.new_folder_id to CONFORMS folder if project found."""
        print(f"Searching for Frame.io project: {self.project_nickname}")
        client = FrameioClient(self.token)
        projects = client.teams.list_projects(self.team_id)

        for project in projects:
            if project['name'] == self.project_nickname and not project.get('archived') and not project.get('deleted_at'):
                print(f"Found project: {project['name']} (ID: {project['id']})")
                conforms_folder_id = self.find_conforms_folder(project['id'])
                if conforms_folder_id:
                    self.new_folder_id = conforms_folder_id # Set for CONFORMS uploader context
                    print(f"'CONFORMS' folder found with ID: {self.new_folder_id}")
                else:
                    print(f"Warning: 'CONFORMS' folder not found in project '{project['name']}'. Will attempt to create if needed.")
                    self.new_folder_id = None
                return project['root_asset_id'], project['id']

        print(f"Project '{self.project_nickname}' not found.")
        return None, None

    @catch_exception       
    def find_a_fio_asset(self, project_id: str, base_name: str):
        """Finds an asset by base name in a project. Returns (type, id, parent_id) or (None, None, None)."""
        print(f"Searching for asset with base name '{base_name}' in project ID: {project_id}")
        client = FrameioClient(self.token)
        search_results = client.search.library(query=base_name, project_id=project_id, account_id=self.account_id)

        for item in search_results:
            if item['name'].startswith(base_name) and item['type'] in ['file', 'version_stack']:
                print(f"Found asset: {item['name']} (Type: {item['type']}, ID: {item['id']})")
                return item['type'], item['id'], item.get('parent_id')

        print(f"No matching asset found for '{base_name}'.")
        return None, None, None

    @catch_exception
    def find_conforms_folder(self, project_id: str):
        """Finds the 'CONFORMS' folder in a project. Returns folder_id or None."""
        print(f"Searching for 'CONFORMS' folder in project ID: {project_id}")
        client = FrameioClient(self.token)
        search_results = client.search.library(query="CONFORMS", project_id=project_id, account_id=self.account_id, type="folder")

        for item in search_results:
            if item['name'].upper() == "CONFORMS" and item['type'] == "folder":
                print(f"Found 'CONFORMS' folder with ID: {item['id']}")
                return item['id']

        print("'CONFORMS' folder not found.")
        return None
        
    @catch_exception
    def version_upper(self,selection): 
        """Checks Frame.io for existing versions and increments the version of selected Flame items if found."""
        self.project_nickname = flame.projects.current_project.nickname

        root_asset_id, project_id = self.get_fio_projects()
        if not project_id:
            # If project doesn't exist, no versions to check against.
            # This is not an error, just means no versioning against Frame.io will occur.
            print(f"Frame.io project '{self.project_nickname}' not found. Cannot perform Frame.io based version-up check.")
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Info", f"Frame.io project '{self.project_nickname}' not found. Version-up check against Frame.io will be skipped. Clips will be exported with current names.", type="info")
            return

        print(f"Checking for existing versions in Frame.io project: {self.project_nickname} (ID: {project_id}) to perform version-up.")
        for item in selection:
            if not isinstance(item, flame.PyClip):
                print(f"Item '{getattr(item, 'name', 'Unknown type')}' is not a PyClip. Skipping version-up check.")
                continue

            # Ensure clip name is a string and handle potential surrounding quotes from Flame
            clip_name_original = str(item.name)
            clip_name_for_search = clip_name_original.strip("'") # Remove if they exist

            print(f"Checking Frame.io for asset matching Flame clip name: '{clip_name_for_search}'")
            # Search for an asset with the exact clip name
            asset_type, asset_id, _ = self.find_a_fio_asset(project_id, clip_name_for_search)

            if asset_id:
                print(f"Found matching asset '{clip_name_for_search}' (ID: {asset_id}, Type: {asset_type}) on Frame.io. Attempting to version up in Flame.")

                # Try to find the last version pattern (e.g., _v01, _V023)
                # This regex finds the version string and captures the prefix (_v or _V) and the number
                matches = list(re.finditer(r'(_[vV])(\d+)', clip_name_for_search))
                if matches:
                    last_match = matches[-1] # Get the last match
                    prefix = last_match.group(1) # e.g., "_v"
                    version_number_str = last_match.group(2) # e.g., "01"
                    padding = len(version_number_str)
                    
                    next_version_number = int(version_number_str) + 1
                    new_version_digits = f"{next_version_number:0{padding}d}" # Format with original padding

                    # Reconstruct the new name by replacing only the last version found
                    start_index = last_match.start()
                    end_index = last_match.end()
                    new_clip_name = clip_name_for_search[:start_index] + prefix + new_version_digits + clip_name_for_search[end_index:]

                    # Update the Flame item's name
                    # If original name had quotes, re-add them for consistency if Flame expects that.
                    # However, item.name should handle this correctly.
                    item.name = new_clip_name
                    print(f"Successfully versioned up Flame clip: '{clip_name_for_search}' to '{new_clip_name}'")
                else:
                    message = f"Clip '{clip_name_for_search}' found on Frame.io, but its name does not contain a recognized version pattern (e.g., '_v01', '_V01'). Automatic version-up in Flame skipped."
                    print(message)
                    flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Versioning Info", message, type="info")
            else:
                print(f"No asset matching '{clip_name_for_search}' found on Frame.io. No version-up performed in Flame for this item.")
        # No "else" here for "if project_id" because the return at the start handles it.

#-------------------------------------#
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
