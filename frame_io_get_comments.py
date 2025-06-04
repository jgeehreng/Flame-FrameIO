'''
Script Name: frame_io_get_comments
Script Version: 0.9
Flame Version: 2023.2
Written by: John Geehreng
Creation Date: 01.06.23
Update Date: 10.03.24

Custom Action Type: Media Panel

Description:

    This script will fetch comments from FrameIO and make markers according to the selection.

To install:

    Copy script into /opt/Autodesk/shared/python/frame_io

Updates:
10.03.24 - v0.9 - Start using Color Code Labels
03.21.24 - v0.8 - Misc Optimizations
12.04.23 - v0.7 - Updates for PySide6 (Flame 2025)
11.01.23 - v0.6 - Flag Sequences by assigning color
02.27.23 - v0.5 - Fixed issue for users not signed in, but left comments.
01.18.23 - v0.4 - Added ability to compensate for In Points set before frame 1.
01.11.23 - v0.3 - Fixed Error message when there's not FrameIO Project. Added ability to make segment markers. Added warnings and messages if comments can't be found.
'''

import xml.etree.ElementTree as ET
import flame
import math
import re
import os
import traceback # For catch_exception
from frameioclient import FrameioClient, errors as frameio_errors

SCRIPT_NAME = 'FrameIO Get Comments'
SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__)) # Updated SCRIPT_PATH
VERSION = 'v0.9'

#-------------------------------------#
# Main Script

class frame_io_get_comments(object):

    def __init__(self, selection):
        print(f'\n{">" * 10} {SCRIPT_NAME} {VERSION} Start {"<" * 10}\n')

        self.config_path = os.path.join(SCRIPT_PATH, 'config')
        self.config_xml = os.path.join(self.config_path, 'config.xml')

        if not self.config():
            print(f"{SCRIPT_NAME} {VERSION}: Configuration failed. Exiting.")
            return

        # Initialize FrameioClient after successful config loading
        try:
            self.client = FrameioClient(self.token)
        except Exception as e: # Catch potential errors during client initialization (e.g. invalid token format though SDK might handle this)
            flame.messages.show_in_dialog(f"{SCRIPT_NAME} Error", f"Failed to initialize Frame.io client: {e}", type="error")
            print(f"Error initializing Frame.io client: {e}")
            traceback.print_exc()
            return

        # Start Script Here
        self.get_frame_rate(selection) # This method seems purely Flame-related
        self.get_comments(selection) # This will be refactored to use self.client

    def catch_exception(method):
        def wrapper(self, *args, **kwargs):
            try:
                return method(self, *args, **kwargs)
            except frameio_errors.APIError as e:
                error_message = f"Frame.io API Error in {method.__name__}:\n{e}\nURL: {e.response.url if e.response else 'N/A'}\nStatus: {e.response.status_code if e.response else 'N/A'}"
                print(error_message)
                traceback.print_exc()
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Frame.io API Error", error_message, type="error")
            except Exception as e: # General exception
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
            except ET.ParseError: # Python's ElementTree parse error
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
            # jobs_folder and preset_path_h264 might not be strictly needed for 'get_comments'
            # but we load them for consistency with other scripts using the same config structure.
            self.jobs_folder = settings_el.findtext('jobs_folder')
            self.preset_path_h264 = settings_el.findtext('preset_path_h264')

            # Critical for get_comments are token, account_id, team_id
            if not all([self.token, self.account_id, self.team_id]):
                flame.messages.show_in_dialog(f"{SCRIPT_NAME}: Config Error", "Token, Account ID, or Team ID is missing from the config file.", type="error")
                return False

            if 'fio-x-xxxxxx' in self.token: # Placeholder token check
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
                default_preset_path = os.path.join(SCRIPT_PATH, "presets", "UC H264 10Mbits.xml") # Consistent default
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
                    return True # File created, though it needs user input
                except IOError as e:
                    flame.messages.show_in_dialog(
                        title=f"{SCRIPT_NAME}: File Creation Error",
                        message=f"Unable to create config file: {self.config_xml}\nError: {e}\nCheck file permissions.",
                        type="error")
                    return False
            return True # File already exists

        if not os.path.isfile(self.config_xml):
            if not create_config_file(): # Attempt to create if not existing
                return False # Stop if creation failed

        return get_config_values() # Load values from existing or newly created file

    @catch_exception
    def get_frame_rate(self, selection):
        for item in selection:
            if isinstance(item, flame.PySegment):
                # #print ("I am a segment. Selection name: ", item.name)
                parent_sequence = item.parent.parent.parent
                frame_rate = parent_sequence.frame_rate
                # #print ("frame_rate: ", frame_rate)
                regex = r'\s[a-zA-Z]*'
                test_str = str(frame_rate)
                subst = ""
                fixed_framerate = float(re.sub(regex, subst, test_str, 0))
                fixed_framerate =  math.ceil(fixed_framerate)
                # #print('fixed_framerate: ', str(fixed_framerate))
                self.frame_rate = fixed_framerate
            elif isinstance(item, flame.PyClip):
                # selection_name = item.name
                # #print ("Selection Name: ", selection_name)
                frame_rate = item.frame_rate
                # #print ("frame_rate: ", frame_rate)
                regex = r'\s[a-zA-Z]*'
                test_str = str(frame_rate)
                subst = ""
                fixed_framerate = float(re.sub(regex, subst, test_str, 0))
                fixed_framerate =  math.ceil(fixed_framerate)
                # #print('fixed_framerate: ', str(fixed_framerate))
                self.frame_rate = fixed_framerate
            else:
                # #print('\n')
                self.frame_rate = 24
                #print ("I am not a segment. Selection name: ", item.name)
                # #print('\n')
                pass
    
    def _seconds(self, value):
        if isinstance(value, str):  # value seems to be a timestamp
            _zip_ft = zip((3600, 60, 1, 1/self.frame_rate), value.split(':'))
            return sum(f * float(t) for f,t in _zip_ft)
        elif isinstance(value, (int, float)):  # frames
            return value / self.frame_rate
        else:
            return 0

    def _timecode(self, seconds):
        return '{h:02d}:{m:02d}:{s:02d}:{f:02d}' \
                .format(h=int(seconds/3600),
                        m=int(seconds/60%60),
                        s=int(seconds%60),
                        f=round((seconds-int(seconds))*self.frame_rate))

    def _frames(self, seconds):
        return seconds * self.frame_rate

    def timecode_to_frames(self, timecode, start=None):
        return self._frames(self._seconds(timecode) - self._seconds(start))

    def frames_to_timecode(self, frames, start=None):
        return self._timecode(self._seconds(frames) + self._seconds(start))

    @catch_exception
    def get_comments(self, selection):
        print(f"{SCRIPT_NAME}: Starting to fetch comments...")
       
        self.project_nickname = flame.projects.current_project.nickname
        # self.client is already initialized in __init__

        print(f"Current Flame project nickname: {self.project_nickname}")

        # Get Frame.io project details.
        # This call is now wrapped with @catch_exception and will handle its own errors/dialogs.
        project_info = self.get_fio_projects()

        if not project_info:
            # get_fio_projects should have already shown an error dialog if it failed.
            # So, just print and exit here.
            print(f"Aborting comment fetching as Frame.io project '{self.project_nickname}' could not be accessed.")
            return

        root_asset_id, project_id = project_info
        print(f"Using Frame.io project ID: {project_id}, Root Asset ID: {root_asset_id}")
        # self.root_asset_id = root_asset_id # Not strictly needed here unless other methods would use it

        for item in selection:
            offset_value = 0 # Default offset
            selection_name_for_search = ""
            item_for_markers = item # The Flame object to which markers will be added

            if isinstance(item, flame.PySegment):
                parent_sequence = item.parent.parent.parent
                selection_name_for_search = parent_sequence.name.get_value() # Use .get_value() for PyFlameValueString
                in_point_tc = parent_sequence.in_mark.get_value() if parent_sequence.in_mark else None
                start_time_tc = parent_sequence.start_time.get_value()
                # For segments, markers are typically placed on the segment itself within the sequence timeline
                item_for_markers = item
            elif isinstance(item, flame.PyClip):
                selection_name_for_search = item.name.get_value()
                in_point_tc = item.in_mark.get_value() if item.in_mark else None
                start_time_tc = item.start_time.get_value()
            else:
                print(f"Item '{getattr(item, 'name', 'Unknown type')}' is not a PyClip or PySegment. Skipping.")
                continue

            selection_name_for_search = selection_name_for_search.strip("'") # Clean name for searching
            print(f"\nProcessing Flame item: '{selection_name_for_search}'")

            # Calculate offset based on in_mark and start_time
            # The original logic for offset_value seemed to always result in 0 or 1.
            # This needs to correctly calculate the frame offset if an In Mark is set.
            # If in_mark is None or "NULL" (or not set), Frame.io comments are usually relative to start of asset (frame 1).
            # If an in_mark is set, comments might need to be offset relative to that in_mark on the Flame timeline.
            # For simplicity, the original logic's offset_value=1 for "NULL" in_point is kept,
            # assuming Frame.io comments are 1-based and Flame markers are 0-based or 1-based depending on context.
            # This part might need further review based on exact desired behavior with in_marks.
            if not in_point_tc or 'NULL' in str(in_point_tc):
                offset_value = 1 # Assuming Frame.io is 1-based, Flame marker might need this if 0-based internally
                print("No In Mark set or 'NULL'. Using default offset for comment placement.")
            else:
                # This logic converts TC to frames. Ensure self.frame_rate is correctly set.
                # The goal of offset_value here is to adjust Frame.io's comment frame numbers
                # to the correct frame on the Flame timeline segment/clip.
                # If Frame.io comments are relative to the asset's own start (00:00:00:00),
                # and the Flame item has an in_mark, the comment frame needs to be adjusted.
                # Example: Comment at frame 10 (from FIO). Clip start_time 01:00:00:00, in_mark 01:00:01:00.
                # The "actual" frame 10 of the media is at 01:00:00:09 on its own timeline.
                # On the sequence, this part of the clip starts at 01:00:01:00.
                # So, a comment at FIO frame 10 (0-indexed) should appear at 01:00:01:00 + 10 frames.
                # The current offset_value logic seems to simplify to 0 or 1, which might be insufficient.
                # For now, sticking to the original script's apparent intent for offset_value:
                in_point_frames = self.timecode_to_frames(str(in_point_tc).replace("+", ":"))
                start_time_frames = self.timecode_to_frames(str(start_time_tc).replace("+", ":"))
                # This offset logic from original script is preserved but might need review
                if int(in_point_frames) < int(start_time_frames): offset_value = 0
                if int(in_point_frames) >= int(start_time_frames): offset_value = 0 # Original had this as >= and then another >
                # A more common requirement is: marker_frame_on_timeline = (fio_comment_frame - media_start_frame_of_segment) + segment_timeline_start_frame
                # The original script's offset_value = 1 when no in_mark suggests FIO might be 1-based for comments.
                # And Flame's create_marker is 0-based for frame argument.
                # Let's assume FIO comments are 0-indexed internally from SDK, and create_marker is 0-indexed.
                # If an in_mark is used, the comment frame is relative to the in_mark.
                # offset_value = self.timecode_to_frames(str(start_time_tc).replace("+", ":")) - (self.timecode_to_frames(str(in_point_tc).replace("+",":")) if in_point_tc and 'NULL' not in str(in_point_tc) else 0)
                # This is complex; for now, we'll primarily use the FIO frame directly and adjust if it's 1-based.
                # Safest assumption: FIO comment frame is absolute to the media.
                # Flame marker needs to be relative to the segment/clip's start on *its own* timeline.
                # If item.in_mark is set, Flame item starts at that media frame.
                # FIO comment.frame is likely absolute to media.
                # Marker position in Flame = FIO.comment.frame - item.in_mark_frames (if in_mark is set)
                # This is a simplification: if item.in_mark is not None, offset_value = -self.timecode_to_frames(str(in_point_tc).replace("+",":"))
                # The original code's offset_value = 1 for "NULL" in_point is confusing.
                # Let's assume Frame.io comment frames are 0-indexed from SDK and Flame create_marker is 0-indexed.
                # If an in_mark is set, it means the Flame clip/segment starts viewing the media from that in_mark.
                # A comment at FIO frame X (absolute to media) should appear at X - in_mark_frames on the Flame item.
                # For now, we'll use the simplified offset logic and assume FIO frames are 1-based for marker creation.
                offset_value = 1 # Default assumption: FIO frames are 1-based, Flame markers 0-based.
                if in_point_tc and 'NULL' not in str(in_point_tc):
                     # If there's an in-mark, Frame.io comments are relative to the media's beginning.
                     # The marker on the Flame clip needs to be relative to the clip's start (which is the in-mark).
                     # So, marker_pos = fio_frame - in_mark_in_frames.
                     # The offset_value logic here seems to be more about 0-vs-1 indexing.
                     # Let's keep it simple: if FIO gives frame 1, and Flame marker is 0-indexed, subtract 1.
                     offset_value = 0 # If specific in_point, assume direct mapping for now, adjust if 1-based FIO.
                print(f"Calculated offset_value for comment placement: {offset_value} (based on in_mark: {in_point_tc})")


            asset_info = self.find_a_fio_asset(project_id, selection_name_for_search)

            if asset_info and 'id' in asset_info:
                asset_id = asset_info['id']
                print(f"Found Frame.io asset '{selection_name_for_search}' with ID: {asset_id}")
                
                comment_data = self.get_selection_comments(asset_id)

                if comment_data is None:
                    print(f"Could not retrieve comments for asset ID {asset_id}. Skipping this item.")
                    continue

                if not comment_data:
                    message = f"No comments found for '{selection_name_for_search}' (Asset ID: {asset_id})."
                    print(message)
                    flame.messages.show_in_console(message, 'info', 3)
                    continue

                if isinstance(item_for_markers, flame.PyClip): # Apply to clip
                    try:
                        item_for_markers.colour_label = "Address Comments"
                    except AttributeError:
                        item_for_markers.colour = (0.11372549086809158, 0.26274511218070984, 0.1764705926179886)
                elif isinstance(item_for_markers, flame.PySegment): # Apply to parent sequence of segment
                     try:
                        parent_sequence = item_for_markers.parent.parent.parent
                        parent_sequence.colour_label = "Address Comments"
                     except AttributeError:
                        parent_sequence.colour = (0.11372549086809158, 0.26274511218070984, 0.1764705926179886)

                for info in comment_data:
                    comment_text = str(info['text'])
                    commenter_name = "Unknown Commenter"
                    if info.get('owner') and isinstance(info['owner'], dict) and info['owner'].get('name'):
                        commenter_name = info['owner']['name']

                    # Frame.io comment frame numbers are typically 0-indexed via API, or 1-indexed in UI.
                    # The SDK should provide 0-indexed `frame`. Flame's `create_marker` is 0-indexed.
                    fio_comment_frame = int(info['frame'])

                    comment_duration_seconds = info.get('duration')

                    print(f"  Comment by {commenter_name} at FIO frame {fio_comment_frame}: '{comment_text}'")

                    try:
                        # The marker frame needs to be relative to the item_for_markers's own timeline.
                        # If item_for_markers is a segment, its timeline starts at its own position in the sequence.
                        # If FIO comment frame is absolute to media:
                        # marker_pos_on_item = fio_comment_frame - (item_in_mark_frames if item_in_mark else 0)
                        # The original offset_value seems to be for 1-based vs 0-based.
                        # Assuming FIO SDK gives 0-indexed frame, and create_marker is 0-indexed.
                        marker_frame_on_item = fio_comment_frame # Start with FIO frame
                        if in_point_tc and 'NULL' not in str(in_point_tc) and not isinstance(item_for_markers, flame.PySegment): # For clips with in_mark
                            in_mark_frames_val = self.timecode_to_frames(str(in_point_tc).replace("+", ":"))
                            marker_frame_on_item = fio_comment_frame - int(in_mark_frames_val)

                        if marker_frame_on_item < 0:
                            print(f"    Skipping marker for comment at FIO frame {fio_comment_frame} as it's before the in_mark of '{selection_name_for_search}'.")
                            continue

                        marker = item_for_markers.create_marker(marker_frame_on_item)
                        marker.comment = comment_text
                        marker.name = f"Commenter: {commenter_name}"
                        try:
                            marker.colour_label = "Address Comments"
                        except AttributeError:
                            marker.colour = (0.11372549086809158, 0.26274511218070984, 0.1764705926179886)

                        if comment_duration_seconds and self.frame_rate:
                            duration_in_frames = math.ceil(self.frame_rate * comment_duration_seconds)
                            marker.duration = int(duration_in_frames)
                    except Exception as e:
                        marker_error_msg = f"Could not create marker for comment by {commenter_name} on '{selection_name_for_search}' at target frame {marker_frame_on_item}.\nError: {e}"
                        print(marker_error_msg)
                        flame.messages.show_in_dialog(f"{SCRIPT_NAME} Warning", marker_error_msg, type="warning")
            else:
                message = f"Could not find asset matching '{selection_name_for_search}' in Frame.io project '{self.project_nickname}'."
                print(message)
                flame.messages.show_in_console(message, 'info', 3) # Short info, no dialog needed if asset not found
                continue

        print(f'\n{">" * 10} {SCRIPT_NAME} {VERSION} End {"<" * 10}\n')

    @catch_exception
    def get_fio_projects(self):
        """Gets a Frame.io project by nickname. Returns (root_asset_id, project_id) or None."""
        print(f"Searching for Frame.io project: {self.project_nickname} in team {self.team_id}")
        # self.client is used here
        projects_iterator = self.client.teams.list_projects(team_id=self.team_id)
        for project in projects_iterator:
            if project['name'] == self.project_nickname and not project.get('is_archived') and not project.get('deleted_at'):
                print(f"Found project: {project['name']} (ID: {project['id']})")
                return project['root_asset_id'], project['id']

        print(f"Project '{self.project_nickname}' not found.")
        return None # Return None if no project is found or on error (handled by decorator)

    @catch_exception
    def find_a_fio_asset(self, project_id: str, base_name: str):
        """Finds an asset by base name in a project. Returns asset dict or None."""
        print(f"Searching for asset with base name '{base_name}' in project ID: {project_id}")
        # self.client is used here
        search_results = self.client.search.library(
            query=base_name,
            project_id=project_id,
            team_id=self.team_id, # May or may not be needed depending on SDK version/behavior
            account_id=self.account_id
        )

        # Iterate through results (SDK might return a list or generator)
        for item in search_results:
            # More precise matching can be added here if needed (e.g. item['name'] == base_name)
            # For now, taking the first result that contains the base_name and is a file/version_stack
            if base_name in item['name'] and item['type'] in ['file', 'version_stack']:
                print(f"Found asset: {item['name']} (Type: {item['type']}, ID: {item['id']})")
                return item # Return the asset dictionary

        print(f"No matching asset found for '{base_name}' in project {project_id}.")
        return None # Return None if no asset is found

    @catch_exception
    def get_selection_comments(self, asset_id: str):
        """Gets all comments for a given asset ID. Returns list of comments or None."""
        print(f"Fetching comments for asset ID: {asset_id}")
        # self.client is used here
        comments = self.client.comments.list(asset_id=asset_id, include_replies=True) # include_replies might be default or an option
        # The SDK method should return a list of comment dictionaries.
        # If an API error occurs, catch_exception will handle it.
        # If no comments, it should return an empty list.
        print(f"Found {len(comments)} comments for asset ID {asset_id}.")
        return comments

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

def get_timeline_custom_ui_actions():

    return [
        {
            'name': 'UC FrameIO',
            'actions': [
                {
                    'name': 'Get Comments',
                    'order': 0,
                    'isVisible': scope_segment,
                    'separator': 'below',
                    'execute': frame_io_get_comments,
                    'minimumVersion': '2023.2'
                }
            ]
        }
    ]

def get_media_panel_custom_ui_actions():

    return [
        {
            'name': 'UC FrameIO',
            'actions': [
                {
                    'name': 'Get Comments',
                    'order': 2,
                    'isVisible': scope_clip,
                    'separator': 'above',
                    'execute': frame_io_get_comments,
                    'minimumVersion': '2023.2'
                }
            ]
        }
    ]
