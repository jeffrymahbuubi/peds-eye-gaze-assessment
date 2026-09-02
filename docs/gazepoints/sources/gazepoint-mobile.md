---
title: "GP3-Mobile Reference Guide V4"
source_pdf: "Gazepoint Mobile.pdf"
source_dir: resources/gazepoints/documents/
pages: 14
doc_revision: not stated in document
topic: mobile
parser: NetMind parse_pro (netmind-parse-pdf-mcp 0.1.7)
parsed: 2026-08-27
fidelity: verbatim
figures: not extracted; each image marked [FIGURE], captions retained
parser_corrections:  # NetMind mangled these identifiers; corrected against a pdftotext extraction
  - { from: "NSIROLSession WSocket", to: "NSURLSession WebSocket", occurrences: 1 }
---
GP3-Mobile
Reference Guide

[FIGURE]

# Table of Contents

| Technical Specifications & Requirements | 3 |
|---|---|
| Hardware Components | 4 |
| Hardware Assembly | 5 |
| Software Setup | 6 |
| Android (Chromecast) Setup | 7 |
| iOS Setup | 8 |
| Eye Tracker Setup | 9 |
| Calibration - Gazepoint Control | 10 |
| Calibration - Web App | 11 |
| Calibration - Device Screen Configuration | 12 |
| Calibration - Connect to Gazepoint Control | 13 |
| Calibration - Calibrate User | 14 |

# Technical Specifications & Requirements

## Specifications

| Sampling Rate | 60 Hz or 150 Hz |
|---|---|
| Accuracy | 0.5° - 1° |
| Spatial Resolution (RMS) | 0.1 |
| Eye Tracking Mode | Binocular |
| Operating Distance | 38 cm - 56 cm |
| Tracking Range (Head Box) | 23 cm x 18 cm |
| Calibration | 5 point calibration, www.gp3mobile.com |
| Tracking Recovery Time | < 50 ms |
| System Latency | < 50 ms (end to end from event to API output) |
| Data Connection | USB 3.0 x 2 |
| Dimensions | 23 cm x 28 cm x 16 cm |
| Weight | 1150 g |
| Eyewear Compatibility | Works with most glasses and contact lenses |
| Supported Device Size | Maximum 15 inch screen width and 8 inch screen height |

## Requirements

| Processor | Intel i5 or i7 or AMD Ryzen 7 |
|---|---|
| Memory | 8 GB RAM |
| OS | Windows 10 or 11 64-bit |

# Hardware Components

The GP3-Mobile system will require assembly when first unpacking.

1. Mobile device holder

a. Device holder

b. Sticky pad

2. Base stand

a. Gazepoint GP3-Mobile eye tracker and USB-micro 3.0 cable

b. Video Capture device, HDMI cable and USB-C 3.0 cable

3. Chromecast with USB-micro cable

4. Lightning to HDMI adapter

5. USB hub

[FIGURE]

# Hardware Assembly

First, remove the base stand from the box. Place the stand on a flat surface with the rubber feet facing downwards. Insert the device holder into the channel on top of the base stand, and slide to the front of the base stand and gently tighten the device holder thumbscrew to lock the position. Place the provided sticky pad on top of the device holder. Place the mobile device (Android or iOS) on top of the sticky pad.

Note that it is important that you install the software before connecting the GP3-Mobile to the computer to ensure that the correct drivers are used. See following page for details.

[FIGURE]

# Software Setup

Visit www.gazept.com/downloads to download the latest version of Gazepoint software. Use all default options for the installation.
Password: gazepointsw4u!

Run Gazepoint Analysis and click the registration button. Enter the key provided. Verify that the registration title is the Mobile Edition.

Launch Gazepoint Analysis and open a new project. Under "Media List", select the "+" button to add a new mobile media item.

You will see the output of the mobile display capture from the Chromecast (Android) or iOS device in the main window.

[FIGURE]

## Android (Chromecast) Setup

Android devices connect to the Gazepoint GP3-Mobile system using the Chromecast streaming media player. Ensure the mobile device and Chromecast device are using the **same internet network** as the PC running the Gazepoint software. The PC can be used as a hotspot if needed.

At this stage we recommend you pause any firewall or network blocking anti-virus programs as those can easily disrupt the communication between the PC, mobile device, and Chromecast. Once everything is set up you can re-enable the network protection.

The Chromecast USB power and Video Capture device can be connected to the supplied USB hub, and the GP3-Mobile eye tracker should be connected to a separate USB port on the PC if available, or the USB hub if there are insufficient USB ports on the PC.

1. Plug in the Chromecast power cable to a USB port on the PC, and the Chromecast HDMI output to the Video Capture device input port (IN).

2. Using the USB-C cable, connect the Video Capture device to a USB 3.0 port on the PC.

Once the cables have been set up,

1. Set up Chromecast

a. Download and open the Google Home app from the Google App Store

b. Under the Google Home app, select "Add" → "New device"

c. Follow the steps in the app.

2. Cast phone screen to Chromecast

a. In Google Home, select the Chromecast device that has just been set up

b. Select "Cast my screen"

3. At this stage you should see the mobile device image in the Gazepoint Analysis program main window

Note: All devices must be on the same network to communicate properly

[FIGURE]

# iOS Setup

Apple devices connect to the Gazepoint GP3-Mobile system using an HDMI to lightning adapter cable. Ensure the mobile device and Chromecast device are using the **same internet network** as the PC running the Gazepoint software. The PC can be used as a hotspot if needed.

At this stage we recommend you pause any firewall or network blocking anti-virus programs as those can easily disrupt the communication between the PC, mobile device, and Chromecast. Once everything is set up you can re-enable the network protection.

The Video Capture device can be connected to the supplied USB hub, and the GP3-Mobile eye tracker should be connected to a separate USB port on the PC if available, or the USB hub if there are insufficient USB ports on the PC.

1. Connect HDMI/lightning adapter to mobile device.

2. Connect the HDMI cable to the HDMI/lightning adapter and to the Video Capture device input port (IN).

3. Using the USB-C cable, connect the Video Capture device to a USB 3.0 port.

4. At this stage you should see the mobile device image in the Gazepoint Analysis program main window

Note: All devices must be on the same network to communicate properly

[FIGURE]

# Eye Tracker Setup

The following steps are recommended to obtain robust and consistent eye tracking.

1. Run Gazepoint Control to see the tracking window and ensure proper user positioning.

2. Connect the eye tracker (black USB cable) to the computer.

3. Environment Setup

a. Close window blinds, and if possible, place the GP3-Mobile system away from any windows. Sunlight may interfere with tracking, even on an overcast day.

b. Check that reflective surfaces (light fixtures, wall decor) are not in view of the GP3-Mobile eye tracker.

4. Mobile Device

a. Turn off auto-dim and auto-lock features of the device to prevent interruption of a recording.

5. Participant position

a. A chair with adjustable height is recommended to help position the participant.

b. Position the participant such that they are comfortably viewing the device.

c. Using the face image shown in the Gazepoint Control application, adjust the participant position such that they are centered in the image with the depth indicator at the top as close to the middle (green) as possible.

[FIGURE]

[FIGURE]

Adjust participant distance so that the circle depth marker is centered.

# Calibration – Gazepoint Control

Eye gaze calibration on the mobile device takes place within a webpage. Supported browsers are Chrome on Android devices, and Safari on iOS devices. The calibration webpage is hosted by Gazepoint Control on the local internet network and at www.gp3mobile.com when online internet access is available. Ensure that the mobile device and the computer running Gazepoint Control are on the **same network**.

To access the online calibration page, simply point the mobile device browser to www.gp3mobile.com. Note the webpage is not a SSL secured (HTTP not HTTPS) which allows for communication between the webpage and Gazepoint Control in order to animate the calibration process.

To access the local calibration webpage, take the following steps:

1. In Gazepoint Control, open the Settings window

2. In the Gazepoint Control Settings window, locate the Mobile Server Address field

3. On the mobile device, open the internet browser and input the value of the Mobile Server Address in the URL bar and press enter.

4. If the calibration page does not appear, check that all devices are on the same network and that no firewall or virus scanners are blocking the communications.

5. If you change Wi-Fi networks on the devices, we suggest you restart all applications. If communication is still not working try rebooting each device as well. You may need to "cast screen" in Chromecast if the network changes.

[FIGURE]

# Calibration – Web App

The calibration webpage must be viewed as a "web app" in full-screen mode. A web app is an icon (app) on the device home screen. To set this up, perform the following steps:

1. Add calibration website to home screen.

* On Android devices, within Chrome navigate to the "More Options" menu, and select "Add to Home Screen".

* On iOS devices, within Safari open the "Share" menu, and select "Add to Home Screen".

2. Close the browser. Open the calibration webpage using the newly created shortcut on the mobile device home screen.

3. Verify that the address bar is not visible on the calibration page. Verify that the page is not zoomed in.

[FIGURE]

# Calibration – Device Screen Configuration

## Android Bottom Navigation Bar

There may be a bottom navigation bar displayed on some Android devices. You may hide the bottom navigation bar to display the calibration targets in full screen for optimal performance. To do so, please see your phone manual for specific instructions. Hiding the bottom navigation bar may not be possible for all mobile devices.

[FIGURE]

## Landscape Mode

Some mobile devices may have a front camera cutout in the display. This adds a slight shift in the full screen display. For an accurate calibration in landscape mode, position the mobile device such that the camera is on the right-hand side.

[FIGURE]

Rotate mobile device so that the camera is on the right.

## iOS Safari

Safari for iOS 14+ may have an experimental feature turned on which hinders connection with the calibration webpage. If Gazepoint Control automatically disconnects from the mobile device then you may need to disable this feature.

1. Open the Settings app.

2. Navigate to Safari → Advanced → Experimental Features

3. Locate "NSURLSession WebSocket" and disable it.

# Calibration – Connect to Gazepoint Control

On the calibration webpage there is an entry field for IP Address and port number. These are used to connect to Gazepoint Control and are automatically filled when the calibration webpage is first opened. If the IP address field is empty, or the internet network has changed, the IP address can be found by opening the Gazepoint Control Settings options and reading the field “Control Address”. Enter the Control IP address in the webpage, and then select “Connect” to connect the webpage to Gazepoint Control.

Once successfully connected, the calibration webpage will have a “Disconnect” button to disconnect. The “Mobile Status” field in the Gazepoint Control Settings will also say “Connected”.

Press the “Connect” while in the intended device orientation (portrait/landscape). When switching between orientations, disconnect and reconnect.

If the connection fails, please verify:

* The calibration webpage is not connected elsewhere (such as in the browser).

* Check if any PC firewalls or anti-virus software are blocking connection.

[FIGURE]

# Calibration – Calibrate User

Calibration can be initiated from either Gazepoint Control or Gazepoint Analysis. Select the “Calibrate” button. A five-point calibration animation will be shown on the mobile screen. The calibration display contains a single calibration target that the user must track with their eyes.

Once completed, ask the user to look at each calibration position while observing the real-time gaze in Gazepoint Analysis. Try another calibration if the accuracy is low. If the gaze position is completely off, view the participant's face in Gazepoint Control while they look at the calibration points, and ensure the pupils and light reflection off the eye is visible and correctly tracked. Adjust the position of the participant if necessary.

After calibration has been completed, swipe to return to the home screen on the mobile device. Setup of the Gazepoint GP3- Mobile system is now complete.

[FIGURE]
