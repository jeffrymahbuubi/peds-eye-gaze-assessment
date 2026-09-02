---
title: "Gazepoint Analysis User Manual"
source_pdf: "Gazepoint Analysis.pdf"
source_dir: resources/gazepoints/documents/
pages: 27
doc_revision: December 9, 2025
topic: software
parser: NetMind parse_pro (netmind-parse-pdf-mcp 0.1.7)
parsed: 2026-08-27
fidelity: verbatim
figures: not extracted; each image marked [FIGURE], captions retained
parser_corrections:  # NetMind mangled these identifiers; corrected against a pdftotext extraction
  - { from: "AOIXPORT", to: "AOI_EXPORT", occurrences: 1 }
  - { from: "DATETIMEEXPORTLABEL", to: "DATETIME_EXPORTLABEL", occurrences: 1 }
  - { from: "{DATETIME_label}", to: "{DATETIME_LABEL}", occurrences: 1 }
  - { from: "WEB TITLE", to: "WEB_TITLE", occurrences: 1 }
  - { from: "Revisors", to: "Revisitors", occurrences: 1 }
---
GAZEPOINT ANALYSIS
USER MANUAL

# Contents

| 1 | Introduction | 3 |
|---|---|---|
| 2 | Operation | 3 |
| 2.1 | Basic Operation | 3 |
| 2.2 | Create Project | 5 |
| 2.2.1 | Screen Capture | 6 |
| 2.2.2 | Text/Image/Video | 6 |
| 2.2.3 | Web | 6 |
| 2.2.4 | Web Aggregate | 6 |
| 2.2.5 | Mobile Capture | 7 |
| 2.3 | Collect Data mode | 8 |
| 2.4 | Analyze Data mode | 9 |
| 2.4.1 | Playback Controls and Lower Control Bar | 9 |
| 2.4.2 | Visualization Settings | 10 |
| 2.4.3 | Recording List | 11 |
| 2.4.4 | Thinkaloud Settings (UX Edition only) | 12 |
| 2.4.5 | Web Aggregate Data Analysis | 13 |
| 2.4.6 | Areas of Interest (AOIs) | 14 |
| 2.4.7 | AOI Statistics | 15 |
| 2.5 | Import Data | 15 |
| 3 | Export Data | 16 |
| 3.1 | Data Export (CSV) | 16 |
| 3.1.1 | Project Media Fields | 17 |
| 3.1.2 | Sequence Fields | 18 |
| 3.1.3 | Point of Gaze Fields | 18 |
| 3.1.4 | Accessory Fields | 19 |
| 3.1.5 | Eye Data Fields | 20 |
| 3.1.6 | Biometric Fields | 21 |
| 3.1.7 | Marker Tracking Field | 22 |
| 3.1.8 | AOI Field | 22 |
| 3.1.9 | Saccade Fields | 23 |
| 3.1.10 | Video Frame Field | 24 |

| 3.2 | AOI Data Export (CSV) | 24 |
|---|---|---|
| 3.3 | Image Export | 25 |
| 3.4 | Video Export | 25 |
| 3.4.1 | Individual Recordings | 25 |
| 3.4.2 | All Media Items | 25 |
| 3.4.3 | Media Audio | 25 |
| 4 | Registration | 26 |

# 1 Introduction

Gazepoint Analysis provides an easy-to-use, yet powerful system for collecting and analyzing eye-gaze data. The software is offered in 3 editions.

1) **Gazepoint Analysis Standard Edition** – included free with the GP3 eye-tracker and allows for basic screen capture with gaze overlay and heat map visualization as well as raw data export.

2) **Gazepoint Analysis Professional Edition** - enables text, image and video media playback, dynamic web analysis, aggregation of test subjects and dynamic Areas-Of-Interest (AOI's) with statistics.

3) **Gazepoint Analysis UX Edition** - adds the additional ability for Thinkaloud voice capture and webcam video recording which are essential in many usability testing studies.

The software will operate in full feature trial mode for the first 30 days after which it will revert to Standard Edition and allow only Screen Capture media type. If the Professional or UX Editions of the software was purchased, the software license key must be entered for the software to run in the correct version (see Section 4).

# 2 Operation

Note - **Gazepoint Analysis** receives eye tracker data from **Gazepoint Control**. Gazepoint Control needs to run at the same time as Gazepoint Analysis when collecting eye tracking data.

There are two modes of operation for Gazepoint Analysis, **Collect Data mode** and **Analyze Data mode**. The following section describes both modes in reference to screenshots of the user interface.

## 2.1 Basic Operation

Software projects use multiple folders to save and load the recorded data, and to generate the resulting output files. You should create a new folder for each individual project. Projects should not be combined in the same folder.

[FIGURE]

Figure 1 – Project Creation

When you create a new project the following files and folders are created:

* `C:\"Path to Project"\NewProject.pri`: - project file
* `C:\"Path to Project"\user`: - folder where recorded user data is saved
* `C:\"Path to Project"\src`: - folder for source media for stimulus playback
* `C:\"Path to Project"\result`: - folder where exported output files are saved

Figure 2 shows a screenshot of the Gazepoint Analysis main window with the project file manipulation buttons and the gaze tracker calibration button highlighted.

* **New Project**: Create a new project and project folders
* **Open Project**: Load a previously created project and the data form the user folder
* **Save Project**: Save project file
* **Calibrate**: Send calibration command to the eye-tracker (generally it is simpler to calibrate using the Control software directly)

Feedback on the system operation is provided at the bottom status bar:

* **Client**: Identifies if connected to the gaze server (RX) or disconnected (--)
* **Remote**: Identifies if a Gazepoint Remote application is connected (for remote viewing)
* **Recording**: Indicates the current recording status
* **Project**: Current project file

[FIGURE]

Figure 2 - Gazepoint Analysis Screenshot

## 2.2 Create Project

Analysis projects may be of a variety of media types as selected shown in the dialog box below. Note that Mobile Capture media items will only be available if a mobile device test system is used.

[FIGURE]

Figure 3 - Add / Modify Media Item

### 2.2.1 Screen Capture

Screen Capture captures the screen content of the active desktop and records and overlays the eye tracking layer. This is useful for eye tracking studies on media types not supported, video games or custom applications.

### 2.2.2 Text/Image/Video

Text/Image/Video supports the use of rich text (RTF) files, an image file (.png, .jpg) or a video file (.avi, CODEC H.264, DIVX) or any combination of these files, as the project stimulus content. The software provides options to set the media display duration (in seconds). A duration of 0 seconds means the users controls when to move to the next media item via the SPACEBAR key.

The media playback may be continuous in order, randomized, or a combination of both. For example if you have Media A, Media B (randomize selected), Media C and Media D (randomize selected), the playback order will be Media A, Media B or D, Media C and Media B or D, whichever one is not yet played.

Images and videos will be scaled to fit the screen with a fixed aspect ratio. Text RTF files can be created within Analysis, or created in Word or WordPad. For text we recommend a large font centered vertically and horizontally on the screen (margins are available) with a gray/white text on a dark background.

### 2.2.3 Web

A Web media item is used for web page based projects. There are two web modes, Web and Web Aggregate. In most cases where users are free to naturally browse across many pages, the basic Web media type should be used as this uses the default browser selected on the PC. When a recording is initiated, Gazepoint Analysis will start the default browser and load the URL. To end the recording, click Stop Record in Gazepoint Analysis or use the short-cut key CTRL + ALT + S.

### 2.2.4 Web Aggregate

Web Aggregate is used for eye tracking on a web page where multiple user data aggregation is required. The software uses an internal browser based on a Chromium plugin engine for browsing. While most webpages will work, some pages use advanced web features which will not be compatible with whole page screen capture, for example, infinite scrolling and dynamic page resizing.

Buttons on the top left corner control the browser navigation (forward / back / refresh / home). The NEXT button on the top right advances to the next URL if more than one is added, or stops the recording if at the last media item.

Each web page is recorded as a separate entry in the Recording List. Web pages are rendered in the Analysis browser as shown in the figure below.

*Note: if a recording item is deleted, all other recordings linked to the same user will be removed*

[FIGURE]

Figure 4 – Aggregate Analysis Web Browser

### 2.2.5 Mobile Capture

A mobile capture project requires a Gazepoint mobile device stand and eye-tracker. This media type captures the contents of the mobile device screen and overlays gaze data upon it.

Note: Screen Capture, Web or Web Aggregate and Mobile Capture projects cannot be combined with any other media types. Text, Image, Video files can be combined together in a single project.

## 2.3 Collect Data mode

Figure 5 shows the Gazepoint Analysis main window in data capture mode. Collect Data mode is active when the *Collect Data* button is pressed.

Once a project is created, you have the option to add additional media items. On the left hand side, click the *Add* (+ symbol) button.

The control buttons are as follows

| Collect Data: | Data collection mode |
|---|---|
| Start/Stop Record: | Start stop the recording of gaze data CTRL-ALT-R shortcut to start recording CTRL-ALT-S shortcut to stop recording |
| Select Screen: | Select the active desktop for gaze capture for multi-monitor systems |
| Visualization: | Configure the gaze data visualization |
| Gaze Video: | Display the user face captured by the eye tracker |
| Thinkaloud: | Enable Thinkaloud voice recording and webcam recording |
| Show Cursor: | Display cursor position |
| Show AOI: | Display AOI regions and display settings |

A real-time display of the captured screen with gaze data is shown in the primary display window. The data saved for each recording is listed in the *Recording List*.

[FIGURE]

Figure 5 - Gazepoint Analysis Collect Data Screenshot

## 2.4 Analyze Data mode

Analyze Data mode is active when the Analyze Data button is pressed. Figure 6 shows a screenshot of the Gazepoint Analysis in Analyze Data mode. The control buttons are as follows:

| Analyze Data: | Enter Analyze Data mode |
|---|---|
| Visualization: | Configure the gaze data visualization |
| Gaze Video: | Display the user face captured by the eye tracker |
| Thinkaloud: | Thinkaloud voice recording and webcam recording export settings |
| Show Cursor: | Display cursor position |
| AOI: | Display AOI regions and display settings |
| Export: | Export data as an image video, or CSV raw data file |
| Start/Play/Stop/End: | Manipulates the time slider |
| Time Slider: | Controls the current time position |
| Recording List: | Select one or more recordings to view. Set Primary recording. |
| AOI List: | List of AOI regions for the media item. Click + button to add and then drag mouse on Display Window to create. Click Calculate button to compute statistics. |

[FIGURE]

Figure 6 - Gazepoint Analysis Analyze Data Screenshot

### 2.4.1 Playback Controls and Lower Control Bar

Data visualization can be played back using the return to start, play, and skip to end buttons. The playback slider can be clicked and dragged to a particular time position. Clicking in front of the playback slider will fast-forward playback 2 seconds. Clicking before the playback slider will rewind playback 2 seconds. A playback speed button allows 1x, 2x, 4x and 10x playback for longer recordings.

A specific time can be directly entered into the Time box to jump directly to a specific time. Press Tab button to accept the entered value.

The Snapshot button takes a screenshot of the playback data current position and stores the resulting .PNG file in the \result\ folder in the project folder.

The Registration button is used for software registration and license key registration (see Section 4).

### 2.4.2 Visualization Settings

Visualizations settings are available by clicking the Visualization button. There are four visualization types:

| • Fixation Map | The sequence of fixations of each user with the size of graphic proportional to the fixation duration |
|---|---|
| • Heat Map | Illustrates the general regions viewed by the user |
| • Opacity Map | Illustrates what content was seen by the user by hiding unseen content |
| • Bee Swarm | Displays current gaze position (best for aggregate data viewing) |

[FIGURE]

Figure 7 – Visualization Options

Configurable settings are size, transparency, gaze duration, outlier filter, display blink rate, display events and heat map scale.

| • Size | Adjust the size of gaze graphic visualizations |
|---|---|
| • Transparency | Adjust the transparency of gaze graphic visualizations |
| • Gaze Duration | Specifies how much gaze history data to display (in seconds) |
| • Outlier Filter | Set level of outlier data to omit (not applicable for Opacity Map and Bee Swarm) |
| • Heat Map Scale | Set scale of heat map as relative or absolute differences (only applicable for Heat Map) Relative uses the maximum time as the upper limit colored hottest (red). Absolute uses the specified maximum time (in seconds) as the upper limit color (red), any longer durations are the same maximum color. |
| • Show Fixation ID | Show or hide the fixation ID value in Fixation Map mode |
| • Show Fixation Duration | Show or hide the fixation duration value in Fixation Map mode |
| • Display Events | Displays events logged in Remote Viewer |
| • Graphing | Overlay line graphs of selected data streams such as pupil diameter, biometrics, blink rate, etc. Set the maximum and minimum for each variable or auto scale. |

### 2.4.3 Recording List

To view a single recording, uncheck all other recordings except for the recording of interest. This will automatically set the single recording as the PRIMARY recording. For a single recording, the selected user data is shown, however if multiple recordings are selected, the primary recording videos are still shown (eye tracking image, thinkaloud, screencapture, webpage, etc) and ONLY the gaze and mouse data of the non-primary selected recordings are overlaid on the display. The AOIs that are shown on screen will be those drawn on the primary recording selected, see Section 2.4.6 for more details.

Each recording can be assigned specific user data attributes using the User Data settings. Double click a recording user name or select a recording and then click the Settings button to access the user data settings box. The user name, gender and age can be customized to allow for grouping and easier recording analysis. An X/Y pixel offset can be applied to the gaze data if any systematic offsets in the gaze data are seen. A time offset is also available which can time shift the gaze data, primarily used to align multiple Screen Capture recordings of matching content that may have started at different times. Time offset is not possible on Text/Image/Video and Web Aggregate projects.

For privacy reasons it may be desirable to remove the videos of the subject's face, press the Delete Face Video button to remove the face video of the current recording, or the Delete ALL button to remove face videos from all recordings. The primary purpose of the face video is to check for potential issues during data collection (such as a user turning their head away) and so these videos may be deleted with no impact on the gaze data collected.

The Recording List also includes the ability to group selected users based on gender or preset age groups by using the drop down box.

Data from other projects can be imported by using the Import Data Records button in the recording list (see Section 2.5).

[FIGURE]

Figure 8 – User Data Settings

### 2.4.4 Thinkaloud Settings (UX Edition only)

Thinkaloud is supported by Gazepoint Analysis UX Edition and includes webcam and voice audio recording functionality.

The video drop down option allows you to select the desired webcam. The test audio button allows you to test audio recording by recording and playing back a short recording. If audio is not played back, check your default microphone and speakers.

[FIGURE]

Figure 9 – Thinkaloud Settings

### 2.4.5 Web Aggregate Data Analysis

Projects created as Web Aggregate media are recorded as both a continuous video capture of the browser window visible to the user, as well as an entire static screenshot of the web page as an image. When visualizing web content, if the *Zoom In* button (magnifying glass with +) is pressed only the browser window video is shown as it was originally to the user. If the *Zoom Out* button is pressed then the entire static webpage is shown and the dynamic web video is offset onto the page at the correct scroll position. To hide the dynamic web video playback simply click the camera icon above the zoom buttons.

When in the *Zoom in* mode, the *Down arrow* button links the users scroll to the web page scroll position slider on right. When aggregating multiple subjects viewing patterns, it may be desirable to focus on a fixed region of the web page where many people are looking rather than follow only one users scroll position.

To aggregate subjects, simply click the check marks in the Recording list for the users and web pages to merge. You may also right click and select all the same pages by URL or TITLE. NOTE that the PRIMARY user is used as the 'background' image, i.e. the static page and the video overlay, with all other subjects gaze data drawn on the first user's image.

If a web page changes significantly between users, aggregating gaze data of multiple users may not provide meaningful results. In addition, some webpage designs (such as infinite scroll pages) may not be correctly recorded when the static full page capture is performed.

[FIGURE]

Figure 10 - Web Analysis

### 2.4.6 Areas of Interest (AOIs)

For Text, Image and Video media projects, AOIs are assigned to the media item as the same media items are shown for all recordings. For the other media type projects such as Screen Capture, each recording captures content that is different between each user recording and so the AOIs are assigned to an individual recording (the PRIMARY user recording selected). Aggregation is still possible if the capture content is similar, statistics will be computed based on the selected primary recording AOIs.

An AOI maybe be a rectangular shape or an ellipse shape. To create AOIs, select a start time by moving the time slider to the desired time points and draw an AOI frame. If only 1 AOI time point is created, the AOI will start at the current time and last the remainder of media duration. If 2 or more AOI frames are created it is possible to assign the key frame as a START, MIDDLE or END frame. The AOI will interpolate between key frames (to track content movement in videos) and can stop and restart if content disappears and reappears. In the figures below an AOI is created at time 0 second and lasts until 0.489 s. The AOI then disappears, then reappears in a new location at 0.798 s and moves until ending at 1.087 s. The AOI feedback bar near the time slider graphically displays the time over which the AOI is visible.

It is possible to copy and paste AOI key frames using the Copy and Paste buttons as well as CTRL-C and CTRL-V. Double click on the Time, X, Y, Width, Height values to directly set the values (use the PX button to toggle between image pixels and % of the image width/height). All AOI's defined in an Image/Text/Video media item can be copied and pasted to another media item of similar type by right clicking on the media item. All AOI's defined in a recording can be copied and pasted to another recording along with a potential time-shift to align AOI's to account for different start times in screen capture media.

[FIGURE]

Figure 11 - Dynamic AOI Window

[FIGURE]

Figure 12 - Dynamic AOI Window

### 2.4.7 AOI Statistics

To REFRESH the AOI statistic calculations, click the refresh button at the bottom of the AOI List box shown in Figure 6. Certain operations will automatically refresh, however it is a good idea to refresh the statistics before finalizing the results.

A number of statistics may be calculated for the AOI regions. These include:

| Viewed: | # of viewers who looked at the AOI |
|---|---|
| 1st Viewed: | Average time to first view of the AOI |
| Viewed Time (s): | Average time spent viewing the AOI |
| Viewed Time (%): | Average percent of total time spent viewing the AOI |
| Revisitors: | # of viewers who looked at the AOI more than one time |
| Revisits: | Average number of revisits made by the revisitors |
| Clicks: | Number of left cursor clicks |

If biometrics data is available, each data signal is averaged over the duration of the AOI and the summary per AOI can be found in the data summary export CSV file (see Data Export section below).

## 2.5 Import Data

If a project is copied to multiple separate workstations for recording, the import feature can be used to combine the data recordings into a single project provided the project file is not edited between the workstations. The import dialog is loaded by clicking the import button below the Recording List (see center button Figure 5). The import dialog allows you to browse to the project to import. The media items in the project to import MUST be the same as the current project. To ensure this it is best to have simply copied the master project to the secondary destinations for data collection without making any further modifications to the project.

[FIGURE]

Figure 13 - Import data dialog

# 3 Export Data

Once data collection and the desired analysis setup has been completed, the data may be exported in a variety of formats, including still images, video playback and CSV formatted numeric data.

[FIGURE]

Figure 14 – Export data dialog

## 3.1 Data Export (CSV)

Gaze data is exported in the comma separated value (CSV) format, which is easily imported into Microsoft Excel and other data analysis software tools. Two files are generated for each selected recording: **{RECORDING_NAME}_all_gaze.csv** and **{RECORDING_NAME}_fixations.csv** (where **{RECORDING_NAME}** is the name of the user recording). The **all_gaze** file contains every data record recorded for the user, which allows for the most detailed analysis of every single data point recorded. The **fixation** file contains a subset of the data in which each fixation is listed as a single point.

The columns of data to export may be individually selected. A detailed explanation of the data fields are available in the following sections. The Select AOI button allows you to include AOI data (position and viewed state) within the gaze data CSV export files.

**NOTE:** If the CSV fails to export reporting "Failed to export:" please double check that an anti-virus tool hasn't mistakenly prevent Analysis from generating the report output. It has been noted that on rare occasions the anti-virus tool Avast has been found to occasionally block Analysis from exporting correctly. Simply give permission for Analysis to operate to Avast or other anti-virus tool to correctly export the data.

[FIGURE]

Figure 15 - CSV Data Export Selection

The AOI statistics are summarized and recorded in the **Data_Summary_export_{DATETIME_LABEL}.csv** file. This file contains the statistics for the AOI's on a per user basis, as well as the average over all users selected. The `{DATETIME}` is the date and time the AOI export file was generated, while the `{LABEL}` is a user defined parameter which assists in the clearly labeling the exported files.

### 3.1.1 Project Media Fields

The project media files indicate the sequence of media items being displayed to the participant for that data record. Media fields are used to indicate the sequence of Screen Capture, Image, Video, Text, type media, while Web fields indicate web page type media items.

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| MEDIA_ID | Media ID | Integer | 2 | The ID number of the media item. When a media item is first added to a project, it is assigned an ID of 0 and the ID counter incremented by 1. Subsequent items are assigned an ID similarly. The ID numbers are fixed to the Media items and so if playback is rearranged, the ID numbers remain tied to the assigned item. A numerical ID value can simplify processing in statistical tools such as SPSS, MATLAB, Excel, etc. |
| MEDIA_NAME | Media Name | String | Advertisement1 | The user defined name of the media item. This is a string which can provide a better description of the media item than the ID number. |
| WEB_ID | Web ID | Integer | 1 | The Web ID is similar to the Media ID except for web page content. |
| WEB_TITLE | Webpage Title | String | Google Search | The user defined name of the media item. This is a string which can provide a better description of the web page item than the ID number or URL. |
| WEB_URL | Webpage URL | String | https://news.google.com/ | The URL for the webpage. |

### 3.1.2 Sequence Fields

The sequence data fields are used to indicate the sequence of recorded data records.

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| CNT | Counter | Integer | 45 | The counter data variable is incremented by 1 for each data record sent by the server. Useful to determine if any data packets are missed by the client. |
| TIME(DATE) | Time | Decimal | 4.99716 | The time elapsed in seconds since the start of the recording. Note that the DATE in the header is the computer date and time (e.g. TIME(2024/08/22 08:28:26.460) when the recording started (e.g. at TIME=0) which can be used to synchronize with data collection by other systems that also record the computer date and time (e.g. EEG, etc). |
| TIME_TICK(f) | Time Tick | Integer | 2096547271623 | This is a signed 64-bit integer which indicates the number of CPU time ticks for high precision synchronization with other data collected on the same CPU. The (f) parameter is the frequency of the clock ticks i.e. TIME_TICK(f=10000000). The time tick is from the OpenCV library: https://docs.opencv.org/master/db/de0/group_core_utils.html#gae73f58000611a1af25dd36d496bf4487 |

### 3.1.3 Point of Gaze Fields

The point of gaze (POG) data fields are used to indicate the location on the display the participant was looking at. The Fixation POG is the fixation filtered POG of the 'best' POG which is the average of the left and right eye POG. The X/Y values are fractions of the screen size, so (0, 0) is top left, (0.5, 0.5) is the screen center, and (1.0, 1.0) is bottom right. It is possible to have negative values (i.e. the gaze is above or to the left of the screen) and values greater than 1 (i.e. the gaze is to the right or below the screen). The 'best' of the left/right eye POG data, which is the average of the left eye and right eye POG if both are available, or if not, then of either the left or right eye, depending on which one is valid. For most applications, the FPOG is the correct POG to use as this includes the fixation filtering.

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| FPOGX | Fixation POG X | Decimal | 0.48439 | The X-coordinate of the fixation POG, as a fraction of the screen size. |
| FPOGY | Fixation POG Y | Decimal | 0.24615 | The Y-coordinate of the fixation POG, as a fraction of the screen size. |
| FPOGS | Fixation start time | Decimal | 18.86768 | The starting time of the fixation POG in seconds since the start of the recording. |
| FPOGD | Fixation duration | Decimal | 0.49280 | The duration of the fixation POG in seconds. |
| FPOGID | Fixation ID | Integer | 126 | The fixation POG ID number, incrementing by 1 for each new fixation detected. |
| FPOGV | Fixation valid flag | Integer | 1 | The valid flag with value of 1 (TRUE) if the fixation POG data is valid, and 0 (FALSE) if it is not. FPOGV valid is TRUE ONLY when either one, or both, of the eyes are detected AND a fixation is detected. FPOGV is FALSE when the subject blinks, when there is no face in the field of view, and when the eyes move to the next fixation (i.e. a saccade). |

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| BPOGX | Best POG X | Decimal | 0.32459 | The X-coordinate of the 'best' or average of left and right eye POG, as a fraction of the screen size. |
| BPOGY | Best POG Y | Decimal | 0.51235 | The Y-coordinate of the 'best' or average of left and right eye POG, as a fraction of the screen size. |
| BPOGV | Best POG valid flag | Integer | 1 | The valid flag with value of 1 if the data is valid, and 0 if it is not. |

### 3.1.4 Accessory Fields

The mouse cursor position and button state as well as the keyboard key and key press states are captured and available in the data stream. If a computer system has multiple monitors, the cursor origin (0,0) is with respect to the primary display and can be less than or greater than the screen size if the cursor moves to the secondary screens.

The USER data field requires use of the Open Gaze API (see Gazepoint API manual) and allows for custom data to be embedded in the data stream. This is particularly useful if multiple data recording systems are being used and the USER field can be used to embed synchronization data.

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| CX | Mouse cursor X | Decimal | 0.12500 | The X-coordinate of the mouse cursor, as percentage of the screen size. |
| CY | Mouse cursor Y | Decimal | 0.32500 | The Y-coordinate of the mouse cursor, as percentage of the screen size. |
| CS | Mouse cursor state | Integer | 0 | The state of the mouse cursor buttons, 0 for IDLE, 1 for left mouse button down, 2 for right button down, 3 for left button up, 4 for right button up. |

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| KB | Keyboard key | String | A | The keyboard key pressed, 0-9, A-Z, along with a few special keys such as LEFT, RIGHT, SPACE, and RETURN. Note the ',' character is changed to COMMA to prevent distortion of the CSV export file. Any key pressed that is not recognized will be listed as OTHER. |
| KBS | Keyboard state | Integer | 0 | The state of the keyboard key press, 0 for IDLE, 1 for KEY DOWN (pressed), 2 for KEY UP (released). Note that when typing quickly Windows may report a key release and subsequent key press out of order depending on press-and-hold settings in Windows. A key press-and-hold results in a down, delay, then multiple down status commands, which is behavior configured through Windows settings. An IDLE KBS state corresponds with a blank (space) in the KB data field to simplify parsing. Gazepoint Analysis export of the KB data field clears this value to an empty string when KBS is IDLE. |

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| USER | User data | String | EXP1_START | A user defined data field that can store any string. Often used for synchronization of the gaze data stream with other data collection. Requires the API to set the values. |

### 3.1.5 Eye Data Fields

The eye data fields indicate the location of the eyes in the camera image in percentage of the camera image.

The Blink per Minute data field is computed on a rolling 60 seconds from the start of tracking and so the initial BKPMIN value recorded in a recording will likely be non-zero, i.e. the value at the start of the recording is based on the 60 seconds prior of blinking.

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| LPCX | Left pupil X | Decimal | 0.40525 | The X-coordinate of the left eye pupil in the camera image, as a fraction of the camera image size. |
| LPCY | Left pupil Y | Decimal | 0.32822 | The Y-coordinate of the left eye pupil in the camera image, as a fraction of the camera image size. |
| LPD | Left pupil diameter | Decimal | 15.23866 | The diameter of the left eye pupil in pixels. For pupillometry we recommend using LPMM (see below) which includes head movement compensation. |
| LPS | Left pupil scale | Decimal | 1.04834 | The scale factor of the left eye pupil (unitless). Value equals 1 at the calibration depth, is less than 1 when user is closer to the eye tracker and greater than 1 when user is further away. |
| LPV | Left pupil valid flag | Integer | 1 | The valid flag with value of 1 if the data is valid, and 0 if it is not. |

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| RPCX | Right pupil X | Decimal | 0.45421 | The X-coordinate of the right eye pupil in the camera image, as a fraction of the camera image size. |
| RPCY | Right pupil Y | Decimal | 0.33123 | The Y-coordinate of the right eye pupil in the camera image, as a fraction of the camera image size. |
| RPD | Right pupil diameter | Decimal | 14.98422 | The diameter of the right eye pupil in pixels. For pupillometry we recommend using LPMM (see below) which includes head movement compensation. |
| RPS | Right pupil scale | Decimal | 1.04123 | The scale factor of the right eye pupil (unitless). Value equals 1 at the calibration depth, is less than 1 when user is closer to the eye tracker and greater than 1 when user is further away. |
| RPV | Right pupil valid flag | Integer | 1 | The valid flag with value of 1 if the data is valid, and 0 if it is not. |

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| BKID | Blink ID | Integer | 3 | Each blink is assigned an ID value and incremented by one. The BKID value equals 0 for every record where no blink has been detected. |
| BKDUR | Blink duration | Decimal | 0.016000 | The duration of the preceding blink in seconds. |
| BKPMIN | Blink per minute | Integer | 12 | The number of blinks in the previous 60 second period of time. |

### 3.1.6 Biometric Fields

There are a number of biometric signals available for export. From the eye-gaze tracker the left and right pupil diameter in millimeters, LPMM and RPMM fields, are available. These values are ideally suited for pupillometry as they are compensated for head movement.

If the Gazepoint biometrics hardware is connected, the biometrics fields may also include the analog Dial, GSR / EDA, and heart rate data. The dial is an analog input (0% to 100%) for user self-reporting levels such as engagement. For galvanic skin response / electro dermal activity the data is reported in units of ohms and uS, as well as separated into Tonic and Phasic components. The heart rate is reported in beats per minute, as well as the inter-beat interval (time between R-R pulses) or heart rate variability.

The TTL CSV export corresponds to each TTL pin, i.e. TTL0, TTL1, TTL2, TTL3, etc. The TTL0 channel is an analog input (0 to 1023 value) and the remainder digital inputs (0 to 1). Writing to the TTL channels as an output requires use of the API.

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| LPMM | Left pupil in mm | Decimal | 3.30703 | The diameter of the left eye pupil in units of millimeters. |
| LPMMV | Left pupil valid | Integer | 1 | The valid flag with value of 1 if the data is valid, and 0 if it is not. |

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| RPMM | Right pupil in mm | Decimal | 3.30703 | The diameter of the right eye pupil in units of millimeters. |
| RPMMV | Right pupil valid | Integer | 1 | The valid flag with value of 1 if the data is valid, and 0 if it is not. |

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| DIAL | Analog dial input | Decimal | 0.40270 | The biometrics analog self-reporting dial value as a percentage 0 to 100%. |
| DIALV | Dial valid flag | Integer | 1 | The valid flag with value of 1 if the data is valid, and 0 if it is not. |

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| GSR | GSR/EDA (ohms) | Integer | 695820 | The galvanic skin response / electro dermal activity in units of ohms (typically from 10 kΩ to 2 MΩ). |
| GSR_US | GSR/EDA (uS) | Decimal | 1.43715 | The galvanic skin response / electro dermal activity in units of micro Siemens. |
| GSR_US_TONIC | GSR/EDA (uS) Tonic | Decimal | 1.25499 | The tonic component of the GSR / EDA signal in units of uS |
| GSR_US_PHASIC | GSR/EDA (uS) Phasic | Decimal | 0.18216 | The phasic component of the GSR / EDA signal in units of uS |
| GSRV | GSR/EDA valid flag | Integer | 1 | The valid flag with value of 1 if the data is valid, and 0 if it is not. |

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| HR | Heart rate | Decimal | 53.00000 | The biometrics heart rate in beats per minute. The value reported is averaged over 3 samples to reduce the effect of artifacts due to possible finger motion. |
| HRV | Heart rate valid flag | Integer | 1 | The valid flag with value of 1 if the data is valid, and 0 if it is not. |
| HRP | Heart rate pulse | Integer | 142 | The heart rate pulse signal is unitless but proportional to an ECG signal. The waveform primarily displays the large R pulse signal of the cardiac cycle. The signal is susceptible to noise from finger movement. |
| IBI | Inter-beat Interval | Decimal | 0.781 | The biometrics heart rate interbeat interval. The interbeat interval is the time in seconds between heart beats, also known as the beat to beat interval or RR interval. There is no filtering of this signal and it may be susceptible to noise from finger movement. |

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| TTL0 | TTL channel 0 | Integer | 1015 | The analog value of channel 0 (0-1023). |
| TTL1, TTL2, TTL3, TTL4, TTL5, TTL6 | TTL channel 1 to 6 | Integer | 1 | The digital value of the input channel 0 or 1. |
| TTLV | TTL valid flag | Integer | 1 | The valid flag with value of 1, as of the V2.0 release of the Biometrics system this is always 1. |

### 3.1.7 Marker Tracking Field

If a QR code style marker is worn by the user, the marker of known dimensions can be used to more accurately convert from pixels to metric measurements. The API is required to configure the size of the marker.

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| PIXS | Marker scale factor | Decimal | 0.18972 | The scale conversion factor to convert from pixels (such as pupil size) to millimeters. Multiply the value in pixels by PIXS to convert to millimeters. |
| PIXV | Marker valid flag | Integer | 1 | The valid flag with value of 1 if the data is valid, and 0 if it is not. |

### 3.1.8 AOI Field

The AOI field will list all visible AOIs that the fixation point of gaze has intersected with. Multiple overlapping AOIs are listed with dashes between them, i.e. three overlapping AOIs containing the fixation POG might be listed as AD1-FACE2-LEYE.

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| AOI | Name of the AOI | String | AD1 | List of visible AOIs that contain the fixation POG identified by the current data record (if any). |

Additionally, if `AOI_EXPORT` is checked, then the individual AOIs selected in the Select AOI dialog of the CSV Data Selection will each have 5 columns of data listed as described below. If an AOI moves over time (i.e. using keyframes to animate) then the position of the AOI at any point in time can be determined.

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| AOINAME(X) | X position of the AOI | Float (percent) or Integer (pixel) | 0.240266 | The header will include the NAME of the AOI followed by (X). The value will be 0 if the AOI is not visible. The value can be reported as a percent of the image (same as gaze position) or in pixels. |
| AOINAME(Y) | Y position of the AOI | Float (percent) or Integer (pixel) | 0.294915 | The header will include the NAME of the AOI followed by (Y). The value will be 0 if the AOI is not visible. The value can be reported as a percent of the image (same as gaze position) or in pixels. |
| AOINAME(W) | Width of the AOI | Float (percent) or Integer (pixel) | 0.165242 | The header will include the NAME of the AOI followed by (W). The value will be 0 if the AOI is not visible. The value can be reported as a percent of the image (same as gaze position) or in pixels. |
| AOINAME(H) | Height of the AOI | Float (percent) or Integer (pixel) | 0.318644 | The header will include the NAME of the AOI followed by (H). The value will be 0 if the AOI is not visible. The value can be reported as a percent of the image (same as gaze position) or in pixels. |
| AOINAME(Viewed) | Viewed state indicator | boolean | 1 | The header will include the NAME of the AOI followed by (Viewed). In the all_gaze CSV file the value will be 1 if the AOI is currently viewed (i.e. the current data record gaze was within the AOI region) and 0 otherwise. This value is used to compute the statistics in the Data Summary file on total time viewed, percent viewed, etc. For the fixation CSV file, the value will be 1 if the gaze is fixated on the AOI region, and 0 otherwise. |

### 3.1.9 Saccade Fields

The saccades are the jumps the eyes make between the identified fixations. The magnitude of the saccade is calculated as the norm or distance between two fixations (in pixels). The saccade direction is the angle between each fixation (in degrees from horizontal). These two values are listed as 0 in the data stream until the last valid data record of a fixation at which point the magnitude and direction of the current fixation from the previous fixation is computed.

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| SACCADE_MAG | Saccade magnitude | Decimal | 301.03989 | Magnitude of the saccade between two fixations in units of pixels. |
| SACCADE_DIR | Saccade direction | Decimal | 286.05414 | Direction of the saccade between two fixations in units of degrees from the horizontal. |

### 3.1.10 Video Frame Field

If the media item is a video, the video playback frame number will be listed in this field. As the eye-tracker data rate (60Hz or 150Hz) is typically higher than the video frame rate (30 Hz) there will typically be multiple data records with the same frame number.

| CSV Header ID | Data field | Data type | Example | Description |
|---|---|---|---|---|
| VID_FRAME | Video frame | Integer | 35 | The frame number of the video displayed at the time the data was recorded. |

## 3.2 AOI Data Export (CSV)

When AOI statistics are exported, the data is listed in columns of a CSV text file. The CSV text file columns are as follows:

| Column Heading | Description of Statistic | Description |
|---|---|---|
| Media ID | Media item name |  |
| Media Name | Total duration of stimulus media in seconds (U for User controlled) |  |
| Media Duration | System ID of AOI |  |
| AOI ID | System ID of media item |  |
| AOI Name | Name of AOI |  |
| AOI Start (sec) | Start time the AOI first appeared (usually 0 for images, non-zero for video) |  |
| AOI Duration | Total duration the AOI was visible in seconds |  |
| Viewers (#) | Number of test subjects who looked at the AOI |  |
| Total Viewers (#) | Total number of test subjects aggregated |  |
| Ave Time to 1st View (sec) | Average time from the start of recording to the first fixation within the AOI (value is -1 if it was not viewed) (average over all subjects who viewed AOI) |  |
| Ave Time Viewed (sec) | Average time duration of gaze within the AOI in seconds (average over all subjects who viewed AOI) |  |
| Ave Time Viewed (%) | Average time duration of gaze within the AOI as a percentage of the total viewing time (average over all subjects who viewed AOI) |  |
| Ave Fixations (#) | Average number of fixations for the AOI (average over all subjects who viewed AOI) |  |
| Revisitors (#) * | Number of subjects who had revisits to the AOI (average over all subjects who viewed AOI) |  |
| Average Revisits (#) | Average number of revisits made to the AOI (average over all subjects who viewed AOI) |  |
| Average Clicks (#) | Average number of mouse clicks in the AOI (average over all subjects) |  |
| Ave Dial (0-1) | Average biometrics dial position (percentage from 0 to 1) |  |
| Ave GSR (kOhm) | Average biometrics GSR value |  |
| Ave Heart Rate (BPM) | Average biometrics heart rate |  |
| Ave Interbeat Interval(s) | Average biometrics interbeat interval between heart beats |  |
| Ave Left Pupil (mm) | Average biometrics left pupil diameter in mm |  |
| Ave Right Pupil (mm) | Average biometrics right pupil diameter in mm | *A revisit is where a test subject looks at an AOI and looks away and then looks at the AOI again. |

### 3.3 Image Export

Image snapshots can be created from the display window at any time by clicking the camera icon at the lower right of the time slider. The Snapshot will be recorded in the `\result\` folder and labeled with a timestamp (e.g. Snapshot-03-30-14-01.15.29PM.png). The snapshot resolution depends on the size of the Analysis program window (dynamically resizable). The Export Image button in the Export dialog will generate an image that is equal to the original source media size (pixel width and height). Image snapshots are created based on the position of the time slider.

### 3.4 Video Export

An AVI video file may be generated using the Export Video button of the Export dialog box. The exported video file is labeled **video_export_{DATETIME_EXPORTLABEL}.avi**. The video will show the current selected media item along with any other selected visualizations such as AOI regions, gaze, cursor, etc.

#### 3.4.1 Individual Recordings

If the **individual recordings** box is selected, the export video process will export a video for each individual recording instead of aggregating all selected recordings onto a single video.

#### 3.4.2 All Media Items

If the **all media items** box is selected, the export video process will export a video for each of the media items in the project (only for Text, Image, Video media projects). This allows for batch exporting of potentially long media exports.

#### 3.4.3 Media Audio

If the **Use Media Audio** box is selected, the audio from the source media (if a video has audio) will be overlaid on the exported video.

## 4 Registration

Gazepoint Analysis offers a free 30-day full feature trial of the software. At the end of 30 days, if you have purchased Gazepoint Analysis Profession Edition or Gazepoint Analysis UX Edition, you will need to enter your Software License Key to continue using the software version purchased.

Click the Register button shown in Figure 16 and enter the software key you received when you purchased your copy of Analysis. Click the Activate button to activate the software. You must be connected to the internet for activation to succeed. After activated you no longer need to be connected to the internet. If you need to move your license from one computer to another, simply click the deactivate button and then reactivate on the new computer. Note that there is a limited number of deactivations.

[FIGURE]

Figure 16 - Software Registration

[FIGURE]

Figure 17 - Software Registration Key
