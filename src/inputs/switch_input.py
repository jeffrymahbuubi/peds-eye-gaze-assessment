"""Switch input (plan section 5.3).

v1 supports a keyboard switch (Space/Enter) as a click, with the pointer coming
from gaze (``gaze_switch`` mode) or the mouse (``switch`` mode, for setup
testing). The click detection is a simple rising-edge latch so the same logic
works whether events arrive from PySide6, ``pynput``, or a test harness.

USB-HID / GPIO switches are future work; they only need to feed
:meth:`SwitchInput.press` on activation.
"""

from __future__ import annotations


class SwitchInput:
    """Rising-edge click latch fed by external press/release events."""

    def __init__(self) -> None:
        self._pressed = False
        self._click_latched = False

    def press(self) -> None:
        """Signal that the switch was activated (key down / button press)."""
        if not self._pressed:
            self._click_latched = True
        self._pressed = True

    def release(self) -> None:
        self._pressed = False

    def consume_click(self) -> bool:
        """Return True exactly once per press (one-frame rising edge)."""
        clicked = self._click_latched
        self._click_latched = False
        return clicked
