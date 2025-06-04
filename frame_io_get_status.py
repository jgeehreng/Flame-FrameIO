'''
Script Name: frame_io_get_status
Script Version: 0.2
Flame Version: 2025.1
Written by: John Geehreng
Creation Date: 09.06.24
Update Date: 09.11.24

Custom Action Type: Media Panel

Description:

    This script will fetch the status of any items in FrameIO and color code the Flame selection according to the status on FrameIO.

To install:

    Copy script into /opt/Autodesk/shared/python/frame_io

Updates:
09.11.24 - v0.2 - Added Try/Except for Colour Labels.
09.06.24 - v0.1 - Inception

'''

import xml.etree.ElementTree as ET
import flame
import os
import traceback # For catch_exception
from frameioclient import FrameioClient, errors as frameio_errors

SCRIPT_NAME = 'FrameIO Get Status'
SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__)) # Updated SCRIPT_PATH
VERSION = 'v0.2'

#-------------------------------------#
# Main Script

class frame_io_get_status(object):

    def __init__(self, selection):
        print(f'\n{">" * 10} {SCRIPT_NAME} {VERSION} Start {"<" * 10}\n')

        self.config_path = os.path.join(SCRIPT_PATH, 'config')
        self.config_xml = os.path.join(self.config_path, 'config.xml')

        if not self.config():
            print(f"{SCRIPT_NAME} {VERSION}: Configuration failed. Exiting.")
            return

        try:
            self.client = FrameioClient(self.token)
        except Exception as e:
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to initialize Frame.io client: {e}", type="error")
            print(f"Error initializing Frame.io client: {e}")
            traceback.print_exc()
            return

        # Start Script Here - Call renamed method
        self.sync_frameio_statuses_to_flame(selection)

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
            try:
                xml_tree = ET.parse(self.config_xml)
            except FileNotFoundError:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", f"Config file not found: {self.config_xml}", type="error")
                return False
            except ET.ParseError:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", f"Error parsing config file: {self.config_xml}. Check its XML format.", type="error")
                return False

            root = xml_tree.getroot()

            root = xml_tree.getroot()
            settings_el = root.find('frame_io_settings')
            if settings_el is None:
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", f"Invalid config format: <frame_io_settings> tag not found in {self.config_xml}", type="error")
                return False

            self.token = settings_el.findtext('token')
            self.account_id = settings_el.findtext('account_id')
            self.team_id = settings_el.findtext('team_id')
            self.jobs_folder = settings_el.findtext('jobs_folder') # Kept for consistency
            self.preset_path_h264 = settings_el.findtext('preset_path_h264') # Kept for consistency

            if not all([self.token, self.account_id, self.team_id]):
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", "Token, Account ID, or Team ID is missing from the config file.", type="error")
                return False

            if 'fio-x-xxxxxx' in self.token:
                 flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Warning", f"The token in {self.config_xml} appears to be a placeholder. Please update it with your actual Frame.io API token.", type="warning")

            print(f"{SCRIPT_NAME}: Config loaded successfully.")
            return True

        def create_config_file():
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

        return get_config_values()

    @catch_exception
    def sync_frameio_statuses_to_flame(self, selection): # Renamed method
        print(f"{SCRIPT_NAME}: Starting to sync Frame.io statuses...")
       
        self.project_nickname = flame.projects.current_project.nickname
        # self.client is initialized in __init__
        # self.headers is removed

        print(f"Current Flame project nickname: {self.project_nickname}")

        project_info = self.get_fio_projects()
        if not project_info:
            print(f"Aborting status sync as Frame.io project '{self.project_nickname}' could not be accessed.")
            return # Error dialog should be shown by get_fio_projects

        _root_asset_id, project_id = project_info # Use _ for unused root_asset_id
        print(f"Using Frame.io project ID: {project_id}")

        for item in selection:
            selection_name = item.name
            print ("Selection Name: ", selection_name)

            # find an asset using project and selection name
            search = self.find_a_fio_asset(project_id,selection_name)
            if search != ([], [], []):
                # print('search: ', search)
                type, id, status = search
                # print ("type: ", type)
                # print("id: ", id)
                print("status: ", status)
                print ('\n')
                if status == 'approved':
                    try:
                        item.colour_label = "Approved"
                    except:
                        item.colour = (0.11372549086809158, 0.26274511218070984, 0.1764705926179886)
                elif status == 'needs_review':
                    try:
                        item.colour_label = "Needs Review"
                    except:
                        item.colour = (0.6000000238418579, 0.3450980484485626, 0.16470588743686676)
                elif status == 'in_progress':
                    try:
                        item.colour_label = "In Progress"
                    except:
                        item.colour = (0.26274511218070984, 0.40784314274787903, 0.5019607543945312)
                else:
                    message = f"{selection_name} has no status in FrameIO." 
                    message = f"Asset '{selection_name}' found but has no status (label) in Frame.io."
                    flame.messages.show_in_dialog(f"{SCRIPT_NAME} Info", message, type="info")
                    print(message)

            else: # Asset not found
                message = f"Asset '{selection_name}' not found in Frame.io project '{self.project_nickname}'."
                flame.messages.show_in_console(message, 'info', 6)
                # No dialog for "not found" to avoid too many popups if many items aren't on Frame.io
                print(message)
                continue # Next item

        print(f'\n{">" * 10} {SCRIPT_NAME} {VERSION} End {"<" * 10}\n')

    @catch_exception
    def get_fio_projects(self):
        """Gets a Frame.io project by nickname. Returns (root_asset_id, project_id) or None."""
        print(f"Searching for Frame.io project: {self.project_nickname} in team {self.team_id}")
        projects_iterator = self.client.teams.list_projects(team_id=self.team_id)
        for project in projects_iterator:
            if project['name'] == self.project_nickname and not project.get('is_archived') and not project.get('deleted_at'):
                print(f"Found project: {project['name']} (ID: {project['id']})")
                return project['root_asset_id'], project['id']

        print(f"Project '{self.project_nickname}' not found.")
        # Show dialog here as this is a prerequisite for the script's main function
        flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Frame.io project named '{self.project_nickname}' not found in team ID '{self.team_id}'.", type="error")
        return None

    @catch_exception
    def find_a_fio_asset(self, project_id: str, base_name: str):
        """
        Finds an asset by base_name in a project.
        Returns a dictionary with 'id' and 'label' or None if not found or error.
        """
        print(f"Searching for asset with name '{base_name}' in project ID: {project_id}")
        search_results = self.client.search.library(
            query=base_name,
            project_id=project_id,
            team_id=self.team_id, # May not be strictly necessary if project_id is global
            account_id=self.account_id
        )

        for asset_item in search_results:
            # Exact name match is preferred for status checking
            if asset_item['name'] == base_name and asset_item['type'] in ['file', 'version_stack', 'folder']: # Folders can also have labels
                print(f"Found asset: {asset_item['name']} (ID: {asset_item['id']}, Label: {asset_item.get('label')})")
                return {'id': asset_item['id'], 'label': asset_item.get('label')} # Return dict with id and label

        print(f"No asset with exact name '{base_name}' found in project {project_id}.")
        return None

# Scope
def scope_clip(selection):
    import flame

    for item in selection:
        if isinstance(item, flame.PyClip):
            return True
    return False

def scope_segment(selection):
    import flame
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
                    'execute': frame_io_get_status,
                    'minimumVersion': '2025.1'
                }
            ]
        }
    ]
