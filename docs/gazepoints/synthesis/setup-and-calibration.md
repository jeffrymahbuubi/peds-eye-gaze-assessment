---
title: "GP3 HD Setup and Calibration Runbook"
layer: synthesis
device: GP3 HD (150 Hz)
derived_from:
  - sources/gazepoint-quick-start.md
  - sources/gp3-placement-and-positioning.md
  - sources/gazepoint-vesa-mount.md
  - sources/gazepoint-laptop-mount.md
  - sources/gazepoint-control.md
  - sources/gazepoint-analysis.md
built: 2026-08-27
---

# GP3 HD Setup and Calibration Runbook

End-to-end onboarding, assembled from the quick-start sheet, the placement sheet, the two mount
guides, and the Control manual. Steps are ordered by what actually has to happen first.

## 0. Install the software before connecting the hardware

This is the one ordering constraint that will cost you time if you get it wrong. Both the Control
manual and both mount guides say to install first, because the installer supplies the camera
driver. Plug the tracker in beforehand and Windows may register it as an **Unknown Device**, which
then needs manual cleanup in Device Manager (see `synthesis/troubleshooting.md`).

- Download from <https://gazept.com/downloads/> — the download password appears in the quick-start
  sheet as `gazepointsw4u!`, and the manuals note a password is also issued at time of purchase.
- Accept the default installation options.

## 1. Unbox and check contents

Ships with: the eye tracker (SD or HD), a tripod, and two USB cables — one for camera image data,
one to power the infrared illumination.

Optional accessories: VESA screen mount, laptop mount, DC power supply, biometrics module.

## 2. Mount the tracker

Pick one of three. All three converge on the same geometry in step 3.

**Tripod (default).** Screw the tripod to the GP3 with the thumbscrew, then attach both cables.

**VESA mount** (`sources/gazepoint-vesa-mount.md`) — attaches to the monitor itself.
Kit: 2 VESA rods, 2 VESA arms, 6 black M4 thumbscrews, 4 6-32 ½" washer screws, 4 3M adhesive
strips. Needs a #2 Phillips screwdriver.
1. Attach arms to rods with the washer screws. For 100 mm VESA hole spacing, orient the rods so
   the lower bends point away from the centerline and the arms bend toward it.
2. Attach the tracker to the arms' **top holes** using 2 M4 thumbscrews.
3. Connect the USB power and data cables.
4. Hook the rods under the lower monitor bezel and behind the monitor. Center on the screen, point
   upward at ~45°, as close to the lower bezel as possible.
5. Secure either through the VESA holes (4 M4 thumbscrews) or, if the monitor has none, with two
   3M adhesive strips per rod.
6. Plug both USB cables into the computer.

**Laptop mount** (`sources/gazepoint-laptop-mount.md`).
Kit: the mount and 2 black M4 thumbscrews.
1. Orient the mount with the flared ends toward the back of the tracker; push the tracker's mount
   tabs into the slots and tighten the thumbscrews.
2. Connect the cables, rest it on the keyboard as close to the lower screen edge as possible, and
   angle it up ~45° toward the face.
3. Plug both USB cables into the computer.

Note the mount guides quote ~45° and ~65 cm, consistent with the placement sheet below.

## 3. Position the tracker and the participant

This is the step that determines data quality. The target geometry:

| Parameter | Value |
|---|---|
| Distance to user | **65 cm (~24–25")** — roughly arm's length |
| Height below eye level | **40 cm (~15–16")** |
| Angle | Pointed **upward** toward the face |
| Horizontal | Centered on the screen |
| Placement | As near the **bottom edge of the monitor** as possible |

Sources: `sources/gp3-placement-and-positioning.md`, `sources/gazepoint-quick-start.md`,
`sources/gazepoint-control.md` §3.3.

**If the participant wears glasses:** move the tracker closer, to ~**50 cm (20")**, keep it 40 cm
below eye level, and angle it *more steeply* upward. This moves infrared reflections off the lens
surface downward and away from the pupils. The resulting larger gap between tracker and monitor
base is expected and fine.

**Lighting.** Avoid direct or indirect sunlight on the participant's face; strong sunlight behind
or beside them also interferes. Sunlight carries enough infrared to wash out the tracker's own IR
illumination. Halogen or fluorescent lighting works well — and so does a completely dark room.

**Ergonomics.** Use a height-adjustable chair; it is far easier to move the participant than the rig.

### Live positioning feedback

Start Gazepoint Control and use its on-screen feedback rather than a tape measure:

- A **depth indicator** (a circle below the buttons; also a sliding dot on a Close–Far bar at the
  top) centers and turns **green** at optimal distance, **red** when too close or too far.
- Once gaze tracking is acquired, the eyes are outlined with **green boxes**.
- The participant's eyes should be in focus and framed in the camera image.

### USB connection conflict

The two sources disagree, and you should know which to follow:

- **Quick-start sheet:** "cables must be connected without use of a USB hub" — connect both
  directly to the computer.
- **Control manual §3.2:** connecting directly is ideal, but "a USB 3.0 hub can be used provided it
  is connected to a USB 3.0 (or better) port on the computer."

The Control manual is both more recent (revised March 2025) and more specific, so treat the hub as
*permitted but not preferred*. Given that the GP3 HD needs USB 3.0 to reach 150 Hz at all, the safe
choice on this project is **direct connection for the data cable**. The power cable is unfussy — it
can go to any powered USB port and need not connect to the PC at all (a phone charger works).

## 4. Verify the device before calibrating

In Gazepoint Control's status bar, confirm:

| Field | Expect on a healthy GP3 HD |
|---|---|
| Frame rate | ~150 Hz (~6.7 ms). ~62 Hz (~16.6 ms) means you are on USB 2.0 or CPU-starved |
| Server | Client count and whether data is being transmitted. Double-click to set the API TCP/IP port — it must match Analysis |
| IPD | The inter-pupillary distance the internal model is using |
| Information | Software version, hardware serial, **USB2 or USB3**, and number of trackers |

Also confirm the dim red IR lights are visible behind the front plastic — if not, the power cable
is not supplying the tracker.

## 5. Calibrate

Calibration can be launched from Gazepoint Control or Gazepoint Analysis. The Control manual notes
it is generally simpler to calibrate from Control directly.

The screen blanks and a marker steps through five positions; the participant simply looks at the
marker. Afterwards a green point-of-gaze estimate is drawn so you can sanity-check accuracy by
looking at known points.

**Default 5-point positions** (fractions of screen width/height): centre `(0.50, 0.50)`, then
`(0.85, 0.15)`, `(0.85, 0.85)`, `(0.15, 0.85)`, `(0.15, 0.15)`.

### Calibration window keys

| Key | Action |
|---|---|
| `C` | Re-run the calibration |
| `5` | 5-point calibration — fastest, good accuracy (the default) |
| `9` | 9-point calibration — slightly better accuracy, longer |
| `1` | 1-point calibration — fastest, but **may be very inaccurate**; it only nudges a default set of values |
| `U` | Undo — toggles between the current and previous calibration |
| `S` | Play a short tone at each calibration point |
| `+` / `-` | Increase / decrease the calibration animation timing |
| `D` | Restore default animation times |
| `m` | Confirm the IPD marker has been identified (outlined red) |

Defaults are optimal for most people; a slower speed can improve results with children.

**If calibration is poor, simply run it again.** The manual is explicit that first-time
participants often improve markedly on a second attempt. Ask them to focus on the dot and not to
talk during calibration — people who anticipate where the dot will jump next throw off the result.

### Optional: custom calibration targets

Replace the default animated circles with your own image and sound. Place `CalibPoint1.png` and
`CalibPoint1.mp3` (then `2`, `3`, …) in `C:\Users\<user>\Documents\Gazepoint`. Use a square image
with background RGB `25,25,25` so it blends with the calibration window. Samples ship in the
installation folder under `calibpoints`.

### Optional: IPD calibration for real-world pupil size

Only needed if you require accurate pupil-diameter measurements in millimetres.

Print the marker from the Control manual at exactly **11 mm** square — measure it after printing
with callipers or a ruler, since printers are rarely exact. Tape it to the forehead between the
eyes, press `m` during calibration to confirm it is detected (outlined in red), then calibrate as
normal. The API equivalent is the `MARKER_PIX` command, which takes the marker size in millimetres;
the resulting `PIXS` scale factor converts pixel measurements to millimetres.

## 6. Confirm end-to-end

- Enable the **Gaze pointer** in Control to drive the mouse cursor with gaze — block the sensor to
  regain normal control. Sweep to all corners of the screen.
- Or run a bundled demo (Fruit Ninja Eyeblades ships with source as a Visual Studio project).
- For data collection, launch **Gazepoint Analysis** — remembering that **Control must stay running**,
  since Analysis receives its data from Control. Confirm the Analysis status bar shows `Client: RX`.

## Multi-monitor and multi-tracker notes

- **Select Screen** in Control picks the active display for single-tracker multi-monitor setups.
  Over the API, `SCREEN_SIZE` gets or sets the tracked screen's position and size.
- With multiple trackers, place each below its own screen and calibrate it on that screen. Control
  offers **Enable Auto Switch** and **Next Tracker**; the API equivalent is `TRACKER_ID`, whose
  `SEARCH` parameter accepts `NONE`, `SIMPLE` (switch when both eyes lost), `CURSOR` (follow the
  mouse), or `GAZE` (follow the user's gaze). On a switch, all clients receive an `<UPDATE />` record.

## Related settings worth knowing early

From Control's Settings window (`sources/gazepoint-control.md` §4.2):

- **Enable Auto Gain** — sweeps camera gain low-to-high to lock onto very bright or very dim pupils.
  The first thing to try with very young or elderly participants.
- **Monocular Tracking** — force single-eye tracking; assign the visible eye as Left or Right.
- **Cursor Smoothing** — smoothing applied when gaze (APOG) drives the cursor; defaults to 15 samples.
- **API Port** — TCP/IP port for the Open Gaze API, default **4242**.
- **Mobile Port** — default **4243**, used only for mobile-device calibration.
- **Eye Control Assistant** — connects Control to Microsoft Eye Control accessibility in Windows 10.
