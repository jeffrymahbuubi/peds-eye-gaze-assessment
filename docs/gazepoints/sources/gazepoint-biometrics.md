---
title: "Gazepoint Biometrics User Manual"
source_pdf: "Gazepoint Biometrics.pdf"
source_dir: resources/gazepoints/documents/
pages: 11
doc_revision: December 3, 2023
topic: biometrics
parser: NetMind parse_pro (netmind-parse-pdf-mcp 0.1.7)
parsed: 2026-08-27
fidelity: verbatim
figures: not extracted; each image marked [FIGURE], captions retained
parser_corrections: none required
---
GAZEPOINT BIOMETRICS
USER MANUAL

# Contents

| 1 | Introduction | 2 |
|---|---|---|
| 2 | Technical Specification and Requirements | 2 |
| 3 | Hardware Setup | 3 |
| 3.1 | Data and Power Connections | 3 |
| 3.2 | Biometrics Finger Placement | 3 |
| 4 | Software Setup | 4 |
| 4.1 | Gazepoint Control | 4 |
| 4.2 | Gazepoint Analysis | 5 |
| 4.3 | Lab Streaming Layer | 6 |
| 5 | Biometric Signals | 6 |
| 5.1 | Dial | 6 |
| 5.2 | Galvanic Skin Response | 6 |
| 5.3 | Heart Rate | 6 |
| 5.4 | Heart Rate Pulse | 6 |
| 5.5 | Heart Rate Interbeat Interval | 7 |
| 5.6 | TTL input / output | 7 |
| 6 | Serial Port Communication | 8 |
| 7 | Troubleshooting Tips | 8 |
| 7.1 | Data Not Displayed - Communication Port Driver Not Working | 8 |
| 7.2 | Difficulty Tracking Heart Rate | 10 |

# 1 Introduction

The Gazepoint Biometrics system is a high-performance biometric data capture system that provides gaze data, pupil diameter, heart rate and galvanic skin response (GSR) which also known as electro dermal activity (EDA), TTL input/output as well as a self-reporting dial, all in an easy to use package and at an extremely affordable price.

# 2 Technical Specification and Requirements

| Biometrics | GSR / EDA | Heart Rate | Self-Report Dial | TTL |
|---|---|---|---|---|
| Sampling Rate | 60 Hz / 150 Hz | 60 Hz / 150 Hz | 60 Hz / 150 Hz | 60 Hz / 150 Hz |
| Input Range | 10 kΩ – 10 MΩ 0.1 μS – 100 μS | 35 - 170 BPM | 0 % – 100 % | 0 V – 5 V |
| Sensitivity (ADC) | 10 bit – 4 stage auto gain | 10 bit – 2 stage auto gain | 10 bit | 10 bit |
| Input Protection | Current limiting | Optical | N/A | 10k pullup |
| Frequency Range | DC to 10 Hz | N/A | N/A | N/A |
| Data Connection | USB 2.0 |  |  |  |
| Power Consumption | 30 mA |  |  |  |
| Processor | Intel i5 |  |  |  |
| Memory | 4 GB |  |  |  |
| OS | Window 8/10/11 64 bit |  |  |  |

# 3 Hardware Setup

The Gazepoint biometrics system includes the control module with the self-reporting dial input, GSR/EDA and heart rate sensor module, a 3.5 mm cable and 1 USB mini cable.

[FIGURE]

Figure 1 - Gazepoint Biometrics

## 3.1 Data and Power Connections

Before connecting the hardware to your computer, you should first install the Gazepoint software which will install the required drivers (see software setup below). To connect the biometrics system connect the 3.5 mm cable from the control module to the sensor module (red jack to red jack), and then connect the USB mini cable to the computer.

Ideally the data cables should be connected directly to the USB port on your computer if sufficient ports are available. If there are insufficient USB ports, a USB 3.0 hub can be used provided it is connected to a USB 3.0 (or better) port on the computer.

## 3.2 Biometrics Finger Placement

Any two fingers should work in the sensor module provided they are in contact with the gold sensor plates and the green LED light and optical heart rate sensor. For best fit it is works best to have the shorter finger in the enclosed (green LED) finger position, pushed to the back of the finger shroud.

Do not pull the straps too tightly. If the strap is too tight it will reduce the blood flow through the finger and the pulse will be more difficult to read. If a reading is not shown, loosen the strap a little and wait a few seconds longer.

[FIGURE]

Figure 2 - Biometrics Finger Placement

## 4 Software Setup

The software is available to download from the Gazepoint website here: http://gazept.com/downloads/. A password is required to download the software and will be sent to you at the time of purchase.

The Gazepoint Control software performs the data collection and provides the data to software clients such as Gazepoint Analysis. The software also operates the data server which provides data to third-party programs through the Open Gaze API.

### 4.1 Gazepoint Control

To display biometrics data simply click the Biometrics button to toggle the data display shown below the eye-tracking display window. If --- is shown in place of the data, double check the cable connections described above, as well as possible communication port driver issues listed in the Troubleshooting section below.

The analog engagement dial value reports values from 0 to 100 percent. The GSR/EDA data is shown in two different units, kilo ohms and micro Siemens. The conversion equation to switch between the units is 1 uS = 1 / Ohms * 1,000,000. The heart rate signal is typically around 60 BPM at resting but can vary widely between subjects.

[FIGURE]

Figure 3 - Gazepoint Control Software

## 4.2 Gazepoint Analysis

The biometrics data is streamed into the Gazepoint Analysis system for logging and display. Data is logged to a recording file and can be displayed in line-graph format overlaid on the media content. Average biometric values can be automatically calculated at discrete times as specified by area-of-interest markers designated in the experiment. Please see the Gazepoint Analysis documentation for further information.

## 4.3 Lab Streaming Layer

A lab streaming layer (LSL) app is included in the Gazepoint software installation directory under Gazepoint/demo/lsl/LSLGazepoint.py. The Gazepoint LSL app is a Python script which streams data from Gazepoint Control to the LSL recorder.

The Gazepoint LSL app opens two LSL data streams, *GazepointEyeTracker* and *GazepointBiometrics*. The *GazepointEyeTracker* stream contains point-of-gaze fixation gaze data determined by the Gazepoint fixation filter. The *GazepointBiometrics* stream contains dial, GSR, and heart rate data.

In order to run the Gazepoint LSL app, first ensure PyLSL is installed on your PC. Next, open Gazepoint Control. You can then run LSLGazepoint.py, and start using LSL to stream eye gaze and biometrics data from Gazepoint Control.

# 5 Biometric Signals

## 5.1 Dial

The dial input is designed to allow a user to report a relative level of engagement or any emotional response the experiment calls for. For example the subject may be watching a video clip and be asked to increase the dial when they feel the video content is more interesting / engaging and decrease the dial when the content is of lower interest. This allows a continuous stream of input over the course of the stimulus displayed without having to stop the user to request their feedback.

## 5.2 Galvanic Skin Response / Electrodermal Activity

The galvanic skin response (GSR), also known as electrodermal activity (EDA) is a measure of the resistance of the skin (or the conductance which is 1 / resistance). As sweat glands in the skin activate, even at very small levels, the resistance of the skin changes at a measureable level. The sweat gland activity increases due to psychological or physiological stimulus as controlled by the sympathetic branch of the autonomic nervous system, resulting in a signal which correlates to the degree of the participant response to the stimulus. The tonic and phasic components of the GSR are available in Gazepoint Analysis.

## 5.3 Heart Rate

The heart rate signal is a measure of the heart beats per minute (BPM). To determine the heart rate an optical electrocardiogram (ECG) signal is recorded and the peak (R) signal detected. The time between 3 peaks is averaged to compute the heart rate in BPM. For example, if the average time between pulse maximums is 1 second the heart rate would be 60 BPM.

## 5.4 Heart Rate Pulse

The optical ECG signal is used to determine the heart rate (BPM) from the pulse maximums (R to R times in the figure shown below). The heart rate pulse signal recorded is available through the biometrics system as well, although primarily only the large R signal is visible.

## 5.5 Heart Rate Variability (Interbeat Interval)

In addition to heart rate, the time between heart beats is also available which is known as the interbeat interval (IBI) or heart rate variability. The interbeat time is determined from the peak of the R in the QRS complex to the following R peak and is reported in units of seconds. Note that hand motion can easily corrupt this signal as motion can result in peaks that are not true heart pulses. Post-processing will be required to remove these artifacts, depending on the particular research question of the study.

[FIGURE]

## 5.6 TTL input / output

In addition to the biometric signals, a 7 channel electrical input/output system is available on the bottom of the Dial module. All channels are pulled high internally. The first channel (channel 0) is a 10-bit analog input which maps an analog voltage 0 V – 5 V to values 0 to 1024. Note that USB voltages are rarely exactly 5 V and can vary by 10's of mV and so the maximum voltage may not be 5.0 V. The remaining 6 channels are all digital 0 and 1, corresponding to 0 V and 5 V (TTL standard). The output of all channels are digital as well. As of version 2.0 of the system, the 6 digital channel values are packaged compactly into a single TTL1 string, for example 111111 would mean all digital inputs are high.

# 6 Serial Port Communication

In normal operation the biometrics data is read by the eye-tracking Control software which then integrates the data into the eye-gaze API data stream and is synchronized with all the other data. We recommend using the Control software system to read the biometrics data as this adds a number of processing steps and checks on data validity, however, it is possible to communicate directly with the Biometrics system over the virtual com port (serial port). The com port should be set to 115,000 baud. The possible commands are listed below.

| Command | Description |
|---|---|
| q | Query system version number EG: <ACK ID="GAZEPOINT" VER="2.0" /> |
| v <#> | Specify response data string where <#> is 1, 2 or 3. v 1 = The original V1.X biometrics firmware data string EG: <REC DL="1.000" BPM="54" HR="43" GSR="847123" TTL0="-1" TTL1="-1" /> v 2 = The V2.X biometrics data string EG: <REC T="1280370" D="1.000" B="47.7" H="83" HV="1" I="1.280" G="656956" T0="1013" T1="111111" /> v 3 = The V2.X compact biometrics data string EG: <REC T="1196125" D="1.000" H="89" G="847603" T0="1021" T1="111111" /> |
| s | Send a single data string (see above for example). T is the timestamp, D is dial value, B is beats per minute, H is heart rate pulse, HV is heart rate valid, I is interbeat interval, G is GSR, T0 is the analog input channel and T1 is the digital channels. |
| r | Send a continuous stream of data strings |
| e | End the stream of data strings |
| t <ch> <val> | Set the TTL input/output values. <ch> is the channel number, 0 to 7. If <val> is 0 or 1 the channel specified is switched to an output and set to that value. If <val> is -1 then the channel is reset back to an input. |

# 7 Troubleshooting Tips

## 7.1 Data Not Displayed - Communication Port Driver Not Working

If the biometrics system is plugged in before the software is installed, it is possible that the USB Communication Port driver gets labelled as an 'Unknown Device' or otherwise has difficulty installing in the Windows Device Manager.

To solve this problem, open Device Manager and look for the FT232R USB UART or Unknown Device (usually with an ! symbol on it). Right-click and uninstall. Un-plug the biometrics system, then reinstall the Gazepoint Software suite and then replug the biometrics system to verify the driver is correctly installed. A properly installed communication driver should show up under Ports (COM & LPT) as shown below, in this case COM8. The com port number will likely be different.

[FIGURE]

[FIGURE]

## 7.2 Difficulty Tracking Heart Rate

If the heart rate signal does not display it is most likely due to the finger strap being too loose or too tight. If the strap is loose the finger does not make sufficient contact with the detector. If the strap is tight, the blood flow through the finger is reduced and the pulse signal is again too small to detect. Try loosening or tightening the finger strap while observing the heart rate signal across the Heart Rate display. A good connection is made when you can see defined pulses across the display. Individuals with poor circulation or cold hands may also result in a low heart rate signal.

[FIGURE]
