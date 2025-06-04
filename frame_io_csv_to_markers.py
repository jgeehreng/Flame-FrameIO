'''
Script Name: csv to markers
Script Version: 1.7
Flame Version: 2023.2
Originally Created by: Andy Milkis
Updated by: Jacob Silberman-Baron, John Geehreng
Updated On: 03.01.24

Description:
    Imports a CSV file exported from frame.io and adds markers to a clip in flame. There is no need to modify the CSV downloaded from FrameIO.

Menus:
    Right click on a clip in the Media Panel
        UC FrameIO -> CSV -> Timeline Markers
        Navigate to the CSV file and the script will automatically add markers

    Or, right click on a segment in the timeline to add segment markers
        UC FrameIO -> CSV -> Segment Markers
        Navigate to the CSV file and the script will automatically add markers

    Works for Flame 2023.2 and onward

Updates:
Script Version 1.7 (03.01.24 JG)
    - Use 'Timecode Source In' instead of 'Timecode In'
Script Version 1.6 (02.12.24 JG)
    - Rewrite to be able to use commas and ignore empty rows
Script Version 1.5 (12.03.23 JG)
    - Updates for PySide6 (Flame 2025)
Script Version 1.4 (01.11.23 JG)
    - Added Marker Durations. Added names to be "Commenter: Name of person who made the comment"
    - Uses "Timecode Source" instead of "Timecode In" for search and uses "Frame" for placing markers.
Script Version: 1.3 (11.07.22 JG)
    - Added Flame 2023.1 Browser option, 2023.2 Print to Console message if it can't find the "Timecode In" header, Timeline Segment scopes,
        minimumVersion of 2022 scopes, CSV File Filters, and default path of ~/Downloads
Script Version: 1.2 (7.11.22 JS-B)
    - Removed the CSVFileSelector Object and replaced it with a generic QFileDialog

'''

# ------------- IMPORTS------------------#
import flame
import csv
from flame import PyTime
from os.path import expanduser

# ------------- MAIN SCRIPT------------------#
    
def remove_quotes(string):
    #removes the quotes from the ends of a string
    # '""a""' turns into 'a'
    if string[0] == "\'" and string[-1] == "\'":
        return remove_quotes(string[1:-1])
    elif string[0] == "\"" and string[-1] == "\"":
        return remove_quotes(string[1:-1])
    else:
        return string

def add_markers(selection):
   
    # Modify Default Path for File Browsers:
    default_path = expanduser("~/Downloads")
    
    #Asks the user to select a file
    flame.browser.show(
        title = "Select CSV",
        select_directory = False,
        multi_selection = False,
        extension = "csv",
        default_path = default_path)
    csv_path = (str(flame.browser.selection)[2:-2])
    
    if csv_path:
        print ("CSV Selection: ", csv_path, '\n')
        pass
    else:
        return
    
    # Requrited Header names of the column containing Timecodes and Comments
    tc_header = 'Timecode Source In'
    comment_header = 'Comment'
    
    for flame_obj in selection:
        if isinstance(flame_obj, (flame.PyClip, flame.PySequence, flame.PySegment)):
            if isinstance(flame_obj, flame.PySegment):
                parent_sequence = flame_obj.parent.parent.parent
                frame_rate = parent_sequence.frame_rate
            elif isinstance(flame_obj, flame.PyClip):
                frame_rate = flame_obj.frame_rate
            else:
                continue

        if isinstance(flame_obj, (flame.PyClip, flame.PySequence, flame.PySegment)):
            with open(csv_path, mode='r') as file:
                csv_reader = csv.DictReader(file)
                if tc_header not in csv_reader.fieldnames or comment_header not in csv_reader.fieldnames:
                    print("'Timecode Source In' and/or 'Comment' header not found in CSV file.")
                    flame.messages.show_in_console("'Timecode Source In' and/or 'Comment' header not found in CSV file.", "warning", 5)
                    return
                
                for row in csv_reader:
                    if row[tc_header] and row[comment_header]:
                        timecode =  row[tc_header]
                        # print("Time Code:",timecode)
                        comment = remove_quotes(row[comment_header])
                        # print("Comment:", comment)
                        duration =  row['Duration']
                        # print("Duration:", duration)
                        commenter = remove_quotes(row['Commenter'])
                        # print("Comment by:", commenter)
                        marker_time = PyTime(timecode,frame_rate)
                        
                        # Create Markers
                        try:
                            m = flame_obj.create_marker(marker_time)
                            m.colour = (0.2, 0.0, 0.0)
                            if duration != '0':
                                m.duration = int(duration)
                            m.comment = comment
                            m.name = f"Commenter: {commenter}" 
                        except:
                            pass

# ----------- SCOPES ------------------#
                
def scope_clip(selection):
    for item in selection:
        if isinstance(item, (flame.PyClip, flame.PySegment)):
            return True
    return False

def scope_segment(selection):
    for item in selection:
        if isinstance(item, flame.PySegment):
            return True
    return False

# ----------- MAIN MENU------------------#

def get_timeline_custom_ui_actions():

    return [
        {
            "name": "UC FrameIO",
            "separator": "above",
            "actions": [
                {
                    "name": "CSV -> Segment Markers",
                    "isVisible": scope_segment,
                    "minimumVersion": '2023.2',
                    'order ': 1,
                    "separator": 'above',
                    "execute": add_markers
                }
            ]
        }

     ]


def get_media_panel_custom_ui_actions():

    return [
        {
            "name": "UC FrameIO",
            "actions": [
                {
                    "name": "CSV -> Timeline Markers",
                    "isVisible": scope_clip,
                    "minimumVersion": '2023.2',
                    "separator": 'above',
                    "execute": add_markers
                }
            ]
        }

     ]
