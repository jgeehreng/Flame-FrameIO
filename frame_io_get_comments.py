'''
Script Name: frame_io_get_comments
Script Version: 0.9.1
Flame Version: 2023.2
Written by: John Geehreng
Creation Date: 01.06.23
Update Date: 10.03.24 (Refactored to use frame_io_utils.py)

Custom Action Type: Media Panel

Description:

    This script will fetch comments from FrameIO and make markers according to the selection.

To install:

    Copy script into /opt/Autodesk/shared/python/frame_io
    Ensure frame_io_utils.py is also in this directory.

Updates:
(Refactored to use frame_io_utils.py)
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
    get_asset_comments # Added
)

SCRIPT_NAME = 'FrameIO Get Comments'
SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))
VERSION = 'v0.9.1' # Incremented version

#-------------------------------------#
# Main Script

class frame_io_get_comments(object):

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

        self.get_frame_rate(selection)
        self.get_comments_and_create_markers(selection) # Renamed main processing method

    @frame_io_api_exception_handler
    def get_frame_rate(self, selection): # This remains a local method
        for item in selection:
            if isinstance(item, flame.PySegment):
                parent_sequence = item.parent.parent.parent
                frame_rate = parent_sequence.frame_rate
                regex = r'\s[a-zA-Z]*'
                test_str = str(frame_rate)
                subst = ""
                fixed_framerate = float(re.sub(regex, subst, test_str, 0))
                fixed_framerate =  math.ceil(fixed_framerate)
                self.frame_rate = fixed_framerate
                return # Found framerate from first segment's sequence
            elif isinstance(item, flame.PyClip):
                frame_rate = item.frame_rate
                regex = r'\s[a-zA-Z]*'
                test_str = str(frame_rate)
                subst = ""
                fixed_framerate = float(re.sub(regex, subst, test_str, 0))
                fixed_framerate =  math.ceil(fixed_framerate)
                self.frame_rate = fixed_framerate
                return # Found framerate from first clip
        # Fallback if no clip or segment found in selection or other issue
        self.frame_rate = 24
        print(f"Could not determine framerate from selection, defaulting to {self.frame_rate} fps.")


    # --- Timecode utility methods remain local as they are Flame specific ---
    def _seconds(self, value):
        if isinstance(value, str):
            _zip_ft = zip((3600, 60, 1, 1/self.frame_rate), value.split(':'))
            return sum(f * float(t) for f,t in _zip_ft)
        elif isinstance(value, (int, float)):
            return value / self.frame_rate
        return 0

    def _timecode(self, seconds):
        return '{h:02d}:{m:02d}:{s:02d}:{f:02d}'.format(
            h=int(seconds/3600), m=int(seconds/60%60), s=int(seconds%60),
            f=round((seconds-int(seconds))*self.frame_rate)
        )

    def _frames(self, seconds):
        return seconds * self.frame_rate

    def timecode_to_frames(self, timecode, start=None):
        return self._frames(self._seconds(timecode) - (self._seconds(start) if start else 0))

    def frames_to_timecode(self, frames, start=None):
        return self._timecode(self._seconds(frames) + (self._seconds(start) if start else 0))

    @frame_io_api_exception_handler
    def get_comments_and_create_markers(self, selection): # Renamed from get_comments for clarity
        print(f"{SCRIPT_NAME}: Starting to fetch comments and create markers...")
        self.project_nickname = flame.projects.current_project.nickname
        print(f"Current Flame project nickname: {self.project_nickname}")

        project_details = get_frame_io_project_details(self.client, self.project_nickname, self.team_id, SCRIPT_NAME)
        if not project_details:
            # Dialog handled by decorated get_frame_io_project_details
            print(f"Aborting comment fetching as Frame.io project '{self.project_nickname}' could not be accessed.")
            return

        project_id = project_details['project_id']
        print(f"Using Frame.io project ID: {project_id}")

        for item in selection:
            offset_value = 0
            selection_name_for_search = ""
            item_for_markers = item
            selection_framerate_obj = None # To store Flame's framerate object for duration calc

            if isinstance(item, flame.PySegment):
                parent_sequence = item.parent.parent.parent
                selection_name_for_search = parent_sequence.name.get_value()
                in_point_tc_obj = parent_sequence.in_mark
                start_time_tc_str = parent_sequence.start_time.get_value()
                selection_framerate_obj = parent_sequence.frame_rate
                item_for_markers = item
            elif isinstance(item, flame.PyClip):
                selection_name_for_search = item.name.get_value()
                in_point_tc_obj = item.in_mark
                start_time_tc_str = item.start_time.get_value()
                selection_framerate_obj = item.frame_rate
            else:
                print(f"Item '{getattr(item, 'name', 'Unknown type')}' is not a PyClip or PySegment. Skipping.")
                continue

            selection_name_for_search = selection_name_for_search.strip("'")
            print(f"\nProcessing Flame item: '{selection_name_for_search}'")

            in_point_tc_str = in_point_tc_obj.get_value() if in_point_tc_obj else None

            if not in_point_tc_str or 'NULL' in str(in_point_tc_str):
                offset_value = 0 # Assuming FIO comment frame 0 needs to be Flame marker frame 0
                print("No In Mark set or 'NULL'. Using default offset for comment placement.")
            else:
                # This logic is tricky and depends on how FIO reports comment frames vs Flame's expectations.
                # If FIO comment frame is absolute to media start (0), and Flame clip has in_mark,
                # then marker_pos_in_flame_item = FIO_frame - in_mark_as_frames.
                # The original script's offset was 1 for NULL in_point, suggesting FIO comments might be 1-based in its data.
                # However, SDKs often return 0-based. Assuming 0-based from SDK for now.
                # If FIO comment frame is 0-indexed and create_marker is 0-indexed:
                # offset_value = -self.timecode_to_frames(str(in_point_tc_str).replace("+", ":"))
                # This would make marker_frame = fio_comment_frame + offset_value
                # Let's simplify: marker position is fio_comment_frame - in_mark_frames (if clip)
                # or fio_comment_frame (if segment, assuming comments relative to sequence timeline)
                # The original script's offset logic was complex and potentially incorrect.
                # For now, if an in_mark is set on a clip, we assume comments are relative to the media's start.
                if isinstance(item_for_markers, flame.PyClip):
                     offset_value = -self.timecode_to_frames(str(in_point_tc_str).replace("+", ":"))
                # For segments, markers are on the segment itself, assume FIO comment frame is relative to sequence time.
                # This needs careful validation against actual FIO comment data.
                # For now, keeping offset_value = 0 for segments if in_mark is present.
                print(f"In Mark: {in_point_tc_str}, Start TC: {start_time_tc_str}. Calculated offset_value: {offset_value}")


            asset_info = find_frame_io_asset_by_name(self.client, project_id, selection_name_for_search, self.team_id, self.account_id, SCRIPT_NAME=SCRIPT_NAME)

            if asset_info and 'id' in asset_info:
                asset_id = asset_info['id']
                print(f"Found Frame.io asset '{selection_name_for_search}' with ID: {asset_id}")
                
                comment_data = get_asset_comments(self.client, asset_id, SCRIPT_NAME)

                if comment_data is None:
                    print(f"Could not retrieve comments for asset ID {asset_id} (API error likely). Skipping.")
                    continue

                if not comment_data:
                    message = f"No comments found for '{selection_name_for_search}' (Asset ID: {asset_id})."
                    print(message)
                    flame.messages.show_in_console(message, 'info', 3)
                    continue

                # Apply color label
                target_for_color = item_for_markers if isinstance(item_for_markers, flame.PyClip) else parent_sequence
                try:
                    target_for_color.colour_label = "Address Comments"
                except AttributeError:
                    target_for_color.colour = (0.11372549086809158, 0.26274511218070984, 0.1764705926179886)

                for info in comment_data:
                    comment_text = str(info['text'])
                    commenter_name = info.get('owner', {}).get('name', "Unknown Commenter")
                    fio_comment_frame = int(info['frame']) # Assuming SDK provides 0-indexed frame
                    comment_duration_seconds = info.get('duration')

                    print(f"  Comment by {commenter_name} at FIO frame {fio_comment_frame}: '{comment_text}'")

                    try:
                        # Adjust FIO frame to Flame marker frame
                        # If item is a segment, its 'start_frame' is its position on the sequence.
                        # FIO comment frame is likely relative to the sequence time if asset is the sequence.
                        marker_frame_on_item = fio_comment_frame
                        if isinstance(item_for_markers, flame.PyClip) and in_point_tc_str and 'NULL' not in str(in_point_tc_str) :
                             in_mark_frames_val = self.timecode_to_frames(str(in_point_tc_str).replace("+",":"))
                             marker_frame_on_item = fio_comment_frame - int(in_mark_frames_val)
                        elif isinstance(item_for_markers, flame.PySegment):
                            # For segments, FIO comments are relative to sequence. Marker frame is directly FIO frame.
                            pass


                        if marker_frame_on_item < 0:
                            print(f"    Skipping marker for comment at FIO frame {fio_comment_frame} as it's before the in_mark/start of '{selection_name_for_search}'. Target marker frame: {marker_frame_on_item}")
                            continue

                        marker = item_for_markers.create_marker(int(round(marker_frame_on_item))) # Ensure integer frame
                        marker.comment = comment_text
                        marker.name = f"Commenter: {commenter_name}"
                        try:
                            marker.colour_label = "Address Comments"
                        except AttributeError:
                            marker.colour = (0.11372549086809158, 0.26274511218070984, 0.1764705926179886)

                        if comment_duration_seconds and self.frame_rate:
                            duration_in_frames = math.ceil(self.frame_rate * comment_duration_seconds)
                            if duration_in_frames > 0: # Marker duration must be positive
                                marker.duration = int(duration_in_frames)
                            else: # Frame.io can have 0 duration comments. Flame markers need >0.
                                marker.duration = 1 # Smallest possible duration
                    except Exception as e:
                        marker_error_msg = f"Could not create marker for comment by {commenter_name} on '{selection_name_for_search}' at target frame {marker_frame_on_item if 'marker_frame_on_item' in locals() else fio_comment_frame}.\nError: {e}"
                        print(marker_error_msg)
                        flame.messages.show_in_dialog(f"{SCRIPT_NAME} Warning", marker_error_msg, type="warning")
            else:
                message = f"Could not find asset matching '{selection_name_for_search}' in Frame.io project '{self.project_nickname}'."
                print(message)
                flame.messages.show_in_console(message, 'info', 3)
                continue

        print(f'\n{">" * 10} {SCRIPT_NAME} {VERSION} End {"<" * 10}\n')

    # Local Frame.io helper methods (get_fio_projects, find_a_fio_asset, get_selection_comments) are now removed.

# Scope
def scope_clip(selection):
    # import flame # Not needed here, flame is globally imported
    for item in selection:
        if isinstance(item, flame.PyClip):
            return True
    return False

def scope_segment(selection):
    # import flame # Not needed here, flame is globally imported
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
                    'execute': frame_io_get_comments, # Class name is the callable
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
                    'execute': frame_io_get_comments, # Class name is the callable
                    'minimumVersion': '2023.2'
                }
            ]
        }
    ]
