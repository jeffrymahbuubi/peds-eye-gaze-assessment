---
title: "Troubleshooting"
layer: synthesis
derived_from:
  - sources/gazepoint-control.md
  - sources/gazepoint-biometrics.md
  - sources/gazepoint-analysis.md
  - sources/gazepoint-remote-viewer.md
  - sources/gazepoint-mobile.md
built: 2026-08-27
---

# Troubleshooting

All troubleshooting guidance from the manual set, organised by symptom.

## The GP3 HD is not running at 150 Hz

The single most common GP3 HD issue, and it has one cause: **the tracker is on a USB 2.0 port.**

Check the negotiated bus in the Gazepoint Control status bar (bottom right, *Information*) — it
reports USB2 or USB3. Or query `PRODUCT_ID` over the API, which returns `BUS` and `RATE`. Move the
data cable to a USB 3.0 port.

If the bus is correctly USB 3.0 but the frame rate still reads low, the cause is CPU: the manual
notes the rate should be ~150 Hz (~6.7 ms) and that a lower value means the host needs more
processing power. Recall the spec sheet asks for an i5 minimum, i7 recommended.

Source: `sources/gazepoint-control.md` §6.5, §4.1.

## The tracker appears dead

**No dim red lights behind the front plastic.** The IR illuminators are unpowered or the software
is not running. Check the second USB cable is supplying power, confirm Gazepoint Control is
running, and kill any duplicate Gazepoint Control processes.

**Camera shows a strange split image.** A known, infrequent bug with the Firefly camera on the
first startup after a PC boot or a version upgrade. Restart Gazepoint Control.

Source: `sources/gazepoint-control.md` §6.4.

## Windows shows the camera as "Unknown Device"

Caused by plugging the tracker in **before** installing the software, so the camera driver was
never available.

1. Open Device Manager and find the unknown device.
2. Right-click → **Uninstall**.
3. Unplug the tracker.
4. Reinstall the Gazepoint software package.
5. Reconnect.

A correctly installed driver appears as a **Point Grey Research** device.

Source: `sources/gazepoint-control.md` §6.3.

## The camera sees the eyes but will not lock on

Several artifacts can defeat the tracking algorithm:

| Cause | Remedy |
|---|---|
| **Sunlight** | Its infrared content washes out the tracker's IR sources. Work under halogen or fluorescent light — dark rooms work well too |
| **Hard contact lenses** | They shift position after a blink. Little to be done beyond awareness |
| **Dirty soft contact lenses** | Reduce the specular reflections tracking depends on. Use clean lenses |
| **Dirty or scratched glasses; shiny metal frames** | Clean them; increase the tracker's upward angle |
| **Glittery makeup** | Produces spurious reflections. Avoid |

Source: `sources/gazepoint-control.md` §6.4.

## Difficulty tracking participants with glasses

Infrared reflects off the lens surface back into the camera, masking the pupils. **Tilt the tracker
upward at a steeper angle**, which may also mean seating the participant slightly higher. This
moves the reflections down and away from the pupils.

The placement sheet quantifies it: bring the tracker to ~**50 cm** from the user (instead of 65 cm),
keep it 40 cm below eye level, and angle it more steeply upward. The larger gap this opens between
tracker and monitor base is expected.

Source: `sources/gazepoint-control.md` §6.2, `sources/gp3-placement-and-positioning.md`.

## Difficulty tracking very young or elderly participants

Usually a pupil-brightness problem — very bright pupil responses in children, dim ones in older
participants. Enable **Automatic Gain Sweep** (Enable Auto Gain) in the Settings dialog: the system
cycles gain through its full range to catch problematic eyes.

Source: `sources/gazepoint-control.md` §6.1, §4.2.

## Calibration will not work

- **Run it again.** Many participants need to see the process once before they perform it well; a
  second calibration often fixes it outright.
- Ask the participant to **focus on the dot and not talk** during calibration.
- Watch for **anticipation** — people who predict where the dot will jump next corrupt the result.
- For children, slow the animation with `-` in the calibration window.
- If gaze is wildly off, watch the participant's face in Control while they look at the calibration
  points, and confirm the pupils and corneal reflections are visible and correctly tracked. Adjust
  their position if not.

Source: `sources/gazepoint-control.md` §6.4, §4.3; `sources/gazepoint-mobile.md`.

## Biometrics: no data displayed (`---` shown)

First check the cable connections: the 3.5 mm cable runs from the control module to the sensor
module (**red jack to red jack**), and the USB mini cable to the computer.

If cabling is right, it is a **COM port driver** problem — the same "plugged in before installing"
failure as the camera:

1. Open Device Manager and look for **FT232R USB UART** or an Unknown Device (often flagged with `!`).
2. Right-click → Uninstall.
3. Unplug the biometrics system.
4. Reinstall the Gazepoint software suite.
5. Replug the biometrics system.

A correctly installed driver appears under **Ports (COM & LPT)**, e.g. COM8 — the number will vary.

Source: `sources/gazepoint-biometrics.md` §7.1, §3.1.

## Biometrics: heart rate will not read

Almost always the finger strap tension:

- **Too loose** → insufficient contact with the detector.
- **Too tight** → restricted blood flow, so the pulse is too small to detect.

Adjust while watching the heart rate display; a good connection shows defined pulses marching
across the display. Give it a few seconds to settle after each adjustment.

For placement: any two fingers work provided they contact the gold sensor plates and the green LED
optical sensor. Put the **shorter finger in the enclosed (green LED) position**, pushed to the back
of the finger shroud. Participants with poor circulation or cold hands may read weakly regardless.

Source: `sources/gazepoint-biometrics.md` §7.2, §3.2.

## Analysis: CSV export fails

If export reports `Failed to export:`, suspect **anti-virus interference** before anything else.
The manual names Avast specifically as having been observed blocking Analysis from writing its
report output. Grant Analysis permission in the anti-virus tool and retry.

Source: `sources/gazepoint-analysis.md` §3.1.

## Analysis: no data arriving

Gazepoint Analysis does not talk to the hardware — it receives data from Gazepoint Control.
**Control must be running at the same time.** Confirm the Analysis status bar shows `Client: RX`
rather than `--`.

If it still will not connect, check the API port matches on both sides: double-click the *Server*
field in Control's status bar to set the TCP/IP port, default **4242**.

Source: `sources/gazepoint-analysis.md` §2, §2.1; `sources/gazepoint-control.md` §4.1.

## Remote Viewer will not connect

- Verify the IP address of the Analysis machine is entered correctly.
- Verify the TCP/IP port (**8442** by default) is not blocked by a Windows or router firewall.
- Confirm the software licence key includes Remote Viewer support.
- Gazepoint Analysis must be running on the host.

Find the host IP with `IPCONFIG` on Windows (look for the IPv4 address, e.g. `192.168.1.106`) or
`IFCONFIG` on Mac/Linux. For WAN use, you need a fast synchronous connection — 100 Mbps or better —
and port 8442 open through the firewall; ask your network administrator for the WAN address.

Source: `sources/gazepoint-remote-viewer.md` §4.1, §2.3.

## Remote Viewer: low frame rate

- Ensure at least **20 Mbps** of bandwidth is available per connection.
- Ensure both machines have enough CPU — an i7 is recommended for running Control, Analysis, and
  Remote streaming together.
- **Shrink the Analysis program window.** Image size tracks window size, so a smaller window means
  less data to compress and transmit. Maximum rate is 10 fps regardless.

Source: `sources/gazepoint-remote-viewer.md` §4.2, §2.1, §3.3.

## Mobile: calibration webpage will not connect

Applies to GP3-Mobile only.

- All devices — phone, Chromecast, and PC — must be on the **same network**. The PC can act as a hotspot.
- Pause firewalls and network-blocking anti-virus during setup; re-enable afterwards.
- The calibration page is served over **HTTP, not HTTPS** by design, so that the page can talk to
  Gazepoint Control.
- Check the page is not already connected in another browser tab.
- After changing Wi-Fi networks, restart all applications; reboot the devices if that fails, and
  re-cast the screen on Chromecast.
- Connect while in the **intended device orientation**; disconnect and reconnect when switching
  between portrait and landscape.
- **iOS 14+ Safari:** disable the experimental feature *NSURLSession WebSocket* under
  Settings → Safari → Advanced → Experimental Features. Leaving it on causes Control to drop the
  connection.
- **Landscape mode:** rotate so the camera is on the **right-hand side**, which compensates for the
  display shift caused by front-camera cutouts.

Source: `sources/gazepoint-mobile.md`.

## Cleaning the tracker

Compressed air for dust on the lens. For fingerprints or smudges, use the microfibre cloth bag
supplied with the tracker; for stubborn marks, a little rubbing alcohol on the cloth and a very
gentle wipe.

Worth knowing: only a small circle at the very centre is actually used by the camera, so the system
tolerates most dust and smudges. Cleaning is largely cosmetic and rarely necessary for correct
operation.

Source: `sources/gazepoint-control.md` §6.6.
