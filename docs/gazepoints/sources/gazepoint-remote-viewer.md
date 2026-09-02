---
title: "Gazepoint Remote Viewer User Manual"
source_pdf: "Gazepoint Remote Viewer.pdf"
source_dir: resources/gazepoints/documents/
pages: 9
doc_revision: February 2, 2020
topic: software
parser: NetMind parse_pro (netmind-parse-pdf-mcp 0.1.7)
parsed: 2026-08-27
fidelity: verbatim
figures: not extracted; each image marked [FIGURE], captions retained
parser_corrections: none required
---
GAZEPOINT
REMOTE VIEWER
USER MANUAL

# Contents

| 1 | Introduction | 2 |
|---|---|---|
| 2 | Setup | 2 |
| 2.1 | Requirements | 2 |
| 2.2 | Installation | 2 |
| 2.3 | Connection | 2 |
| 2.3.1 | LAN Connection Users (within the same office sharing the LAN network) | 2 |
| 2.3.2 | WAN Connection Users (connection separated by firewall and the internet) | 3 |
| 3 | Operation | 4 |
| 3.1 | Connection | 4 |
| 3.2 | Analysis Control | 5 |
| 3.3 | Remote Image Transmission | 6 |
| 3.4 | Log Events | 7 |
| 4 | Troubleshooting | 8 |
| 4.1 | Remote does not connect to Analysis | 8 |
| 4.2 | Low frame rate | 8 |

# 1 Introduction

The Gazepoint Remote Viewer module is an add-on tool for the Gazepoint Analysis system. Remote Viewer provides the ability to connect to Gazepoint Analysis from a remote computer and stream the currently active eye-tracking main display contents to the remote station via a LAN/WAN network connection. Remote Viewer has versions for Windows, Mac and Linux.

Remote Viewer functionality is useful for those users who wish to setup observation rooms where the observers are separated from the eye tracking tester and test subject. Multiple Remote Viewer sessions may connect to Analysis at one time.

In addition Remote Viewer provides the capability to embed notes by the observer into the data stream during the experiment.

# 2 Setup

## 2.1 Requirements

Remote Viewer uses TCP/IP to communicate between Analysis and Remote sessions. Each connection requires approximately 20 Mbps of bandwidth. A moderately powerful computer (ideally and i7) is also required to achieve the maximum 10 fps frame rate, at the same time as running the eye-tracker Control and Analysis software. A license purchase of Remote is also required.

## 2.2 Installation

The Remote Viewer is distributed as a separate installer for each operating system. To install Remote Viewer on the remote computer, please download and run the latest Remote installer for the particular operating system you are using from the downloads page: http://www.gazept.com/downloads

## 2.3 Connection

To connect Remote Viewer to a running instance of Analysis, you will need the IP address of the host computer running Analysis and the PORT number. Remote Viewer uses port 8442 by default. At this time Remote uses IPV4 addresses that look like XXX.XXX.XXX.XXX, typically a local address such as 192.168.X.XXX.

### 2.3.1 LAN Connection Users (within the same office sharing the LAN network)

On Windows you can find the IP address of a computer by running the command `IPCONFIG` command from the Windows command prompt. To get the command prompt, click the Windows Start button, then type `CMD` and press enter.

Then type `IPCONFIG` to find the IPV4 Address – i.e. 192.168.1.106.

On Mac and Linux you can start a terminal window and run `IFCONFIG` to determine your IP address.

[FIGURE]

### 2.3.2 WAN Connection Users (connection separated by firewall and the internet)

For WAN connection users you need to have a fast synchronous internet connection, 100Mbps or faster in order to have a reasonably good frame rate with Remote over the WAN connection.

You should contact your network administrator to find out your WAN IP address and also ensure that port number 8442 is open through the firewall.

# 3 Operation

## 3.1 Connection

To connect Remote Viewer to the eye tracking experiment host computer running Gazepoint Analysis, you must have Gazepoint Analysis running on the host computer. Ensure that the software license key includes support for Remote Viewer.

[FIGURE]

Start Remote Viewer on the remote computer and click on the Settings button. Enter the IP of the host computer and click OK. Click the Connect button and verify that the lower right Taskbar confirms the connection.

[FIGURE]

## 3.2 Analysis Control

Remote provides the ability to **Stop** and **Start** recordings in Analysis. Feedback on the recording process is shown in the lower Taskbar.

[FIGURE]

### 3.3 Remote Image Transmission

The images displayed in Analysis are compressed and transmit to the Remote Viewer program at a maximum rate of 10 fps if sufficient processing power and network bandwidth is available.

The image transmit is the same as the image rendered for the Analysis display window. Modifying the size of the Analysis program window allows trading off image quality for frame rate, the smaller the window the smaller the image and therefore less bandwidth required. The frame rate and image size transmit are shown in the lower task bar

Remote can go full screen by clicking the **Full Screen** button which hides all the rest of the controls and maximizes the image displayed. To exit the full screen mode, click on the image or press the escape key.

To save a still image click the **Take Snapshot** button.

[FIGURE]

## 3.4 Log Events

Real-time event observations can be recorded into the gaze tracking data stream by using the **Event** text input field. Events are only recorded if a recording is currently underway. After the data collection is complete, the recorded observations can be played back in Analysis and overlaid on the experiment by enabling the event display under the Analysis Visualizations settings. If multiple Remote clients are connected, an Event text message is also displayed on all Remote sessions.

[FIGURE]

# 4 Troubleshooting

## 4.1 Remote Viewer does not connect to Analysis

- Ensure the IP address of the Analysis computer is entered correctly

- Ensure the TCP/IP PORT is not blocked by a Windows or Router firewall

## 4.2 Low frame rate

- Ensure sufficient bandwidth is available, remote requires at least 20 Mbps of bandwidth.

- Ensure Analysis and Remote PC computers have sufficient CPU processing power.

- Reduce the size of the Analysis program window which will reduce the size of the image transmit across the network.
