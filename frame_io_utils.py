"""
frame_io_utils.py

This module provides utility functions for Frame.io integration with Autodesk Flame,
including configuration management and API error handling.
"""

import os
import xml.etree.ElementTree as ET
import traceback
import flame # Assuming direct import is acceptable for Flame scripts
from frameioclient import FrameioClient, errors as frameio_errors # Added FrameioClient for type hinting
from typing import List, Dict, Any, Optional, Union # For type hints

# Custom Exception for Configuration Errors
class ConfigurationError(Exception):
    """Custom exception for errors related to Frame.io configuration."""
    pass

def load_frame_io_config(config_xml_path: str, script_name: str = "Frame.io Utility") -> Optional[Dict[str, str]]:
    """
    Loads Frame.io configuration from the specified XML file.

    Args:
        config_xml_path (str): The absolute path to the config.xml file.
        script_name (str): The name of the script calling this function, for error messages.

    Returns:
        dict: A dictionary containing configuration values if successful.
              Returns None if an error occurs that is handled by showing a Flame dialog.

    Raises:
        ConfigurationError: If a placeholder token is detected, critical values are missing,
                            the file is not found, or an XML parsing error occurs.
    """
    print(f"{script_name}: Attempting to load configuration from: {config_xml_path}")
    try:
        xml_tree = ET.parse(config_xml_path)
        root = xml_tree.getroot()
    except FileNotFoundError:
        message = f"Configuration file not found: {config_xml_path}"
        # flame.messages.show_in_dialog(f"{script_name}: Configuration Error", message, type="error") # Caller should handle UI
        raise ConfigurationError(message)
    except ET.ParseError as e:
        message = f"Error parsing configuration file: {config_xml_path}. Invalid XML. Error: {e}"
        # flame.messages.show_in_dialog(f"{script_name}: Configuration Error", message, type="error") # Caller should handle UI
        raise ConfigurationError(message)

    config_values = {}
    settings_el = root.find('frame_io_settings')

    if settings_el is None:
        message = f"Invalid config format: <frame_io_settings> tag not found in {config_xml_path}"
        raise ConfigurationError(message)

    required_keys = ['token', 'account_id', 'team_id']
    optional_keys = ['jobs_folder', 'preset_path_h264']

    for key in required_keys + optional_keys:
        config_values[key] = settings_el.findtext(key)

    for key in required_keys:
        if not config_values[key]:
            message = f"Missing critical configuration value for '{key}' in {config_xml_path}."
            raise ConfigurationError(message)

    if config_values['token'] and config_values['token'].startswith('fio-x-xxxxxx'):
        message = f"Placeholder token detected in {config_xml_path}. Please update with your actual Frame.io API token."
        # This is critical, so raise it. The calling script can decide to inform the user.
        raise ConfigurationError(message)

    print(f"{script_name}: Configuration loaded successfully from {config_xml_path}.")
    return config_values

def create_default_frame_io_config(config_xml_path: str, script_name: str = "Frame.io Utility", current_script_path: str = None) -> bool:
    """
    Creates a default Frame.io config.xml file at the specified path.
    (Identical to previous version, just ensuring it's here)
    """
    print(f"{script_name}: Attempting to create default configuration file at: {config_xml_path}")
    config_dir = os.path.dirname(config_xml_path)

    try:
        if not os.path.isdir(config_dir):
            os.makedirs(config_dir, exist_ok=True)
            print(f"Created configuration directory: {config_dir}")
    except OSError as e:
        message = f"Unable to create config directory: {config_dir}\nError: {e}"
        print(f"{script_name} Error: {message}")
        if flame: flame.messages.show_in_dialog(f"{script_name}: File System Error", message, type="error")
        return False

    if current_script_path:
        grandparent_dir = os.path.dirname(os.path.dirname(current_script_path))
        default_preset_path = os.path.join(grandparent_dir, "presets", "UC H264 10Mbits.xml")
    else:
        utils_dir = os.path.dirname(os.path.abspath(__file__))
        default_preset_path = os.path.join(utils_dir, "presets", "UC H264 10Mbits.xml") # Fallback

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
        with open(config_xml_path, 'w') as config_file:
            config_file.write(config_content.strip())
        message = f"Default configuration file created: {config_xml_path}\nPlease update it with your Frame.io credentials and verify paths."
        print(f"{script_name}: {message}")
        if flame: flame.messages.show_in_dialog(f"{script_name}: Configuration Created", message, type="info")
        return True
    except IOError as e:
        message = f"Unable to create config file: {config_xml_path}\nError: {e}"
        print(f"{script_name} Error: {message}")
        if flame: flame.messages.show_in_dialog(f"{script_name}: File System Error", message, type="error")
        return False

def frame_io_api_exception_handler(func):
    """
    Decorator to handle common Frame.io API errors and other exceptions,
    displaying user-friendly messages in Flame.
    (Identical to previous version, just ensuring it's here)
    """
    def wrapper(*args, **kwargs):
        script_name = "Frame.io Operation"
        if args and hasattr(args[0], '__class__') and hasattr(args[0], 'SCRIPT_NAME'):
            script_name = args[0].SCRIPT_NAME
        elif args and isinstance(args[0], FrameioClient) and len(args) > 1 and isinstance(args[1], str) and "SCRIPT_NAME" in kwargs: # Heuristic for standalone calls
             script_name = kwargs.get("SCRIPT_NAME", "Frame.io Utility")


        try:
            return func(*args, **kwargs)
        except frameio_errors.APIError as e:
            status_code = e.response.status_code if e.response is not None else "N/A"
            url = e.response.url if e.response is not None else "N/A"
            # Try to get more detailed error message from response JSON
            try:
                error_details = e.response.json().get("message", str(e)) if e.response is not None else str(e)
            except: # If response is not JSON or other parsing error
                error_details = str(e)

            error_message = (
                f"Frame.io API Error in '{func.__name__}':\n"
                f"Message: {error_details}\n"
                f"Status Code: {status_code}\n"
                f"URL: {url}"
            )
            print(f"{script_name} Error: {error_message}")
            traceback.print_exc()
            if flame: flame.messages.show_in_dialog(f"{script_name}: API Error", error_message, type="error")
            return None
        except ConfigurationError as e:
            error_message = f"Configuration error in '{func.__name__}':\n{e}"
            print(f"{script_name} Error: {error_message}")
            if flame: flame.messages.show_in_dialog(f"{script_name}: Configuration Error", str(e), type="error")
            return None
        except Exception as e:
            error_message_console = f"An unexpected error occurred in '{func.__name__}':\n{traceback.format_exc()}"
            error_message_dialog = f"Error in {func.__name__}:\n{e}\n\nCheck console for more details."
            print(f"{script_name} Error: {error_message_console}")
            if flame: flame.messages.show_in_dialog(f"{script_name}: Unexpected Error", error_message_dialog, type="error")
            return None
    return wrapper

# --- New Shared API Functions ---

@frame_io_api_exception_handler
def get_frame_io_project_details(client: FrameioClient, project_nickname: str, team_id: str, SCRIPT_NAME: str = "Frame.io Utility") -> Optional[Dict[str, str]]:
    """
    Retrieves details for a specific Frame.io project by its nickname.

    Args:
        client: Initialized FrameioClient.
        project_nickname: The nickname of the project to find.
        team_id: The ID of the team the project belongs to.
        SCRIPT_NAME: Name of the calling script for logging.

    Returns:
        A dictionary with 'project_id' and 'root_asset_id' if found, else None.
    """
    print(f"{SCRIPT_NAME}: Searching for Frame.io project named '{project_nickname}' in team ID '{team_id}'.")
    projects_iterator = client.teams.list_projects(team_id)
    for project in projects_iterator:
        if project['name'] == project_nickname and not project.get('is_archived') and not project.get('deleted_at'):
            print(f"{SCRIPT_NAME}: Found project: {project['name']} (ID: {project['id']})")
            return {'project_id': project['id'], 'root_asset_id': project['root_asset_id']}
    print(f"{SCRIPT_NAME}: Project '{project_nickname}' not found in team '{team_id}'.")
    return None

@frame_io_api_exception_handler
def find_frame_io_asset_by_name(client: FrameioClient, project_id: str, asset_name: str, team_id: str, account_id: str, asset_type: Optional[str] = None, SCRIPT_NAME: str = "Frame.io Utility") -> Optional[Dict[str, Any]]:
    """
    Finds an asset by its name within a given project.

    Args:
        client: Initialized FrameioClient.
        project_id: The ID of the project to search within.
        asset_name: The name of the asset to find.
        team_id: The ID of the team (may be optional for some SDK versions if project_id is global).
        account_id: The ID of the account.
        asset_type: Optional. Filter by asset type (e.g., "file", "folder", "version_stack").
        SCRIPT_NAME: Name of the calling script for logging.

    Returns:
        A dictionary containing asset details if found (id, parent_id, label, type, name), else None.
    """
    print(f"{SCRIPT_NAME}: Searching for asset named '{asset_name}' (Type: {asset_type or 'any'}) in project ID: {project_id}")
    search_params = {
        'query': asset_name,
        'project_id': project_id,
        'account_id': account_id,
        'team_id': team_id # Include if required by your SDK version or for specificity
    }
    if asset_type:
        search_params['type'] = asset_type

    search_results = client.search.library(**search_params)

    for item in search_results:
        # Prefer exact name match
        if item['name'] == asset_name:
            print(f"{SCRIPT_NAME}: Found exact match: {item['name']} (ID: {item['id']}, Type: {item['type']})")
            return {
                'id': item['id'],
                'parent_id': item.get('parent_id'),
                'label': item.get('label'),
                'type': item['type'],
                'name': item['name']
            }
    # Fallback for partial match if no exact match found (less ideal for some operations)
    # For now, sticking to exact or first result from query if specific enough.
    # If search_results is not empty and no exact match, the first one might be relevant.
    # However, for finding specific assets like folders, exact match is usually better.
    print(f"{SCRIPT_NAME}: No asset with exact name '{asset_name}' (Type: {asset_type or 'any'}) found in project {project_id}.")
    return None

@frame_io_api_exception_handler
def create_frame_io_project(client: FrameioClient, project_name: str, team_id: str, SCRIPT_NAME: str = "Frame.io Utility") -> Optional[Dict[str, str]]:
    """
    Creates a new Frame.io project.

    Args:
        client: Initialized FrameioClient.
        project_name: The name for the new project.
        team_id: The ID of the team where the project will be created.
        SCRIPT_NAME: Name of the calling script for logging.

    Returns:
        A dictionary with 'project_id' and 'root_asset_id' of the new project, or None on failure.
    """
    print(f"{SCRIPT_NAME}: Creating Frame.io project: {project_name} in team ID {team_id}")
    project_data = client.projects.create(
        team_id=team_id,
        name=project_name,
        private=False # Defaulting to False, make configurable if needed
    )
    if project_data:
        print(f"{SCRIPT_NAME}: Project '{project_name}' created. ID: {project_data['id']}, Root Asset ID: {project_data['root_asset_id']}")
        return {'project_id': project_data['id'], 'root_asset_id': project_data['root_asset_id']}
    return None # Should be handled by decorator if APIError

@frame_io_api_exception_handler
def create_frame_io_folder(client: FrameioClient, parent_asset_id: str, folder_name: str, SCRIPT_NAME: str = "Frame.io Utility") -> Optional[Dict[str, str]]:
    """
    Creates a new folder within a Frame.io project or under another folder.

    Args:
        client: Initialized FrameioClient.
        parent_asset_id: The ID of the parent asset (project root or another folder).
        folder_name: The name for the new folder.
        SCRIPT_NAME: Name of the calling script for logging.

    Returns:
        A dictionary with the new folder's 'id', or None on failure.
    """
    print(f"{SCRIPT_NAME}: Creating folder '{folder_name}' under parent asset ID: {parent_asset_id}")
    # Some SDK versions might use client.assets.create(type="folder", ...)
    # Assuming client.assets.create_folder is available or client.assets.create is adapted.
    # For consistency with FrameioClient v1.1.0 documentation, client.assets.create is more general
    folder_data = client.assets.create(
        parent_asset_id=parent_asset_id,
        name=folder_name,
        type="folder"
    )
    if folder_data:
        print(f"{SCRIPT_NAME}: Folder '{folder_name}' created with ID: {folder_data['id']}")
        return {'id': folder_data['id']}
    return None

@frame_io_api_exception_handler
def add_version_to_asset(client: FrameioClient, existing_asset_id: str, new_asset_id: str, SCRIPT_NAME: str = "Frame.io Utility") -> bool:
    """
    Adds a new version to an existing Frame.io asset.

    Args:
        client: Initialized FrameioClient.
        existing_asset_id: The ID of the asset to version.
        new_asset_id: The ID of the asset that will become the new version.
        SCRIPT_NAME: Name of the calling script for logging.

    Returns:
        True if successful, None on failure (decorator handles dialog).
    """
    print(f"{SCRIPT_NAME}: Adding version (new asset ID: {new_asset_id}) to existing asset ID: {existing_asset_id}")
    client.assets.add_version(asset_id=existing_asset_id, next_asset_id=new_asset_id)
    print(f"{SCRIPT_NAME}: Successfully added version to asset {existing_asset_id}.")
    return True # If no exception, assume success. Decorator returns None on error.

@frame_io_api_exception_handler
def update_asset_label(client: FrameioClient, asset_id: str, label: str, SCRIPT_NAME: str = "Frame.io Utility") -> bool:
    """
    Updates the label (status) of a Frame.io asset.

    Args:
        client: Initialized FrameioClient.
        asset_id: The ID of the asset to update.
        label: The new label (status string, e.g., "approved", "needs_review").
        SCRIPT_NAME: Name of the calling script for logging.

    Returns:
        True if successful, None on failure.
    """
    print(f"{SCRIPT_NAME}: Updating label for asset ID {asset_id} to '{label}'.")
    client.assets.update(asset_id=asset_id, label=label)
    print(f"{SCRIPT_NAME}: Successfully updated label for asset {asset_id}.")
    return True

@frame_io_api_exception_handler
def get_asset_comments(client: FrameioClient, asset_id: str, SCRIPT_NAME: str = "Frame.io Utility") -> Optional[List[Dict[str, Any]]]:
    """
    Retrieves comments for a specific Frame.io asset.

    Args:
        client: Initialized FrameioClient.
        asset_id: The ID of the asset for which to retrieve comments.
        SCRIPT_NAME: Name of the calling script for logging.

    Returns:
        A list of comment dictionaries, or None if an error occurs.
        Returns an empty list if there are no comments.
    """
    print(f"{SCRIPT_NAME}: Fetching comments for asset ID: {asset_id}")
    comments = client.comments.list(asset_id=asset_id, include_replies=True) # Ensure include_replies matches original intent
    if comments is not None: # Check explicitly for None from decorator, though list() usually returns []
        print(f"{SCRIPT_NAME}: Found {len(comments)} comments for asset ID {asset_id}.")
        return comments
    return [] # Return empty list if decorator returned None or if no comments

# (Keep the __main__ block for testing as it was)
if __name__ == "__main__":
    # This block will only execute when frame_io_utils.py is run directly.
    # It's useful for testing the utility functions.

    # To test, you might need to mock the `flame` module if running outside Flame,
    # or ensure this __main__ block is conditional and only runs where `flame` is available.

    print("Testing Frame.io Utilities...")

    # Create a dummy flame module for testing if not in Flame
    if not flame:
        class MockFlameMessages:
            def show_in_dialog(self, title, message, type, buttons=None, cancel_button=None):
                print(f"FLAME DIALOG (Mocked): [{type.upper()}] {title} - {message}")
            def show_in_console(self, message, type, duration):
                 print(f"FLAME CONSOLE (Mocked): [{type.upper()}] {message} (duration: {duration})")

        class MockFlame:
            messages = MockFlameMessages()

        flame = MockFlame()
        print("Mocked Flame module for testing.")


    test_config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_config_dir")
    test_config_file = os.path.join(test_config_dir, "config.xml")

    # Test create_default_frame_io_config
    print(f"\n1. Testing config creation at: {test_config_file}")
    if os.path.exists(test_config_file):
        os.remove(test_config_file)
    if os.path.exists(test_config_dir) and not os.listdir(test_config_dir): # remove if empty
        os.rmdir(test_config_dir)

    created = create_default_frame_io_config(test_config_file, "TestScript", os.path.abspath(__file__))
    if created and os.path.exists(test_config_file):
        print(f"  SUCCESS: Default config created at {test_config_file}")

        # Test load_frame_io_config (with placeholder token error expected)
        print("\n2. Testing config loading (expecting ConfigurationError for placeholder token)")
        try:
            config = load_frame_io_config(test_config_file, "TestScript")
            if config:
                print(f"  LOADED (unexpectedly): {config}")
            else:
                 print(f"  LOADED but returned None (unexpected for placeholder token error with current setup)")
        except ConfigurationError as e:
            print(f"  SUCCESS (Caught Expected Error): {e}")
        except Exception as e:
            print(f"  UNEXPECTED Error during load: {e}")
            traceback.print_exc()

        # Manually create a valid-looking config for further tests
        print("\n3. Creating a 'valid' test config file for further tests...")
        valid_config_content = f"""<settings>
    <frame_io_settings>
        <token>fio-u-VALIDTOKENHERE</token>
        <account_id>valid_account_id</account_id>
        <team_id>valid_team_id</team_id>
        <jobs_folder>/test/jobs</jobs_folder>
        <preset_path_h264>{os.path.join(os.path.dirname(os.path.abspath(__file__)), "presets", "TestPreset.xml")}</preset_path_h264>
    </frame_io_settings>
</settings>
"""
        with open(test_config_file, 'w') as f:
            f.write(valid_config_content)

        print("\n4. Testing config loading with 'valid' data")
        try:
            config = load_frame_io_config(test_config_file, "TestScript")
            if config:
                print(f"  SUCCESS: Config loaded: {config}")
                assert config['token'] == 'fio-u-VALIDTOKENHERE'
            else:
                print("  FAILURE: load_frame_io_config returned None for valid data.")
        except Exception as e:
            print(f"  FAILURE: Error during load of 'valid' data: {e}")
            traceback.print_exc()

    else:
        print(f"  FAILURE: Could not create default config at {test_config_file}")

    # Test decorator (mocking a function that might raise APIError)
    print("\n5. Testing @frame_io_api_exception_handler")

    # Mock frameio_errors.APIError for testing if frameioclient is not fully available
    if 'frameio_errors' not in globals() or not hasattr(frameio_errors, 'APIError'):
        class MockResponse:
            def __init__(self, status_code=500, url="http://mock.api/error"):
                self.status_code = status_code
                self.url = url
            def json(self): # Add json method to mock response
                return {"message": "Mocked API Error Detail"}
        class MockAPIError(Exception):
            def __init__(self, message="Mocked API Error", response=None):
                super().__init__(message)
                self.response = response if response else MockResponse()
        frameio_errors.APIError = MockAPIError
        print("   Mocked frameio_errors.APIError for decorator test.")


    @frame_io_api_exception_handler
    def function_that_raises_api_error(SCRIPT_NAME="DecoratorTest"): # Pass SCRIPT_NAME if not a class method
        print("   Inside function_that_raises_api_error (should not see this if error raised before)")
        raise frameio_errors.APIError("Simulated API Unauthorized")

    @frame_io_api_exception_handler
    def function_with_generic_error(SCRIPT_NAME="DecoratorTest"):
        raise ValueError("Simulated generic error")

    @frame_io_api_exception_handler
    def successful_function(SCRIPT_NAME="DecoratorTest"):
        print("   successful_function executed.")
        return "Success"

    print("   Testing decorator with APIError...")
    result_api_error = function_that_raises_api_error()
    print(f"   Decorator result for APIError: {result_api_error} (Expected None)")

    print("   Testing decorator with generic error...")
    result_generic_error = function_with_generic_error()
    print(f"   Decorator result for generic error: {result_generic_error} (Expected None)")

    print("   Testing decorator with successful function...")
    result_success = successful_function()
    print(f"   Decorator result for success: {result_success} (Expected 'Success')")

    print(f"\nTest config file left at: {test_config_file} for inspection.")
    print("\nFrame.io Utilities Testing Finished.")
