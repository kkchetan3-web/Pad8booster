"""Pad8Booster - a measurement-first optimisation toolkit for the Xiaomi Pad 8.

The project exists because "booster" apps on the Play Store routinely claim
headline speed-ups that no measurement supports. Pad8Booster does the opposite:
every change is applied through a reversible action, and every claim it makes is
derived from a before/after snapshot taken on the user's own hardware.
"""

from __future__ import annotations

__version__ = "1.0.0"

#: Properties of the Xiaomi Pad 8 / Pad 8 Pro used for device verification.
#: Sources: Qualcomm SM8735 (Snapdragon 8s Gen 4), SM8750-AB (Snapdragon 8
#: Elite); HyperOS 3 ships on Android 16 (API 36).
PAD8_SOC_IDS = frozenset({"SM8735", "SM8750", "SM8750-AB", "SM8750-3-AB"})
PAD8_MODEL_TOKENS = ("pad 8", "pad8", "pad_8")
PAD8_MIN_SDK = 35


class Pad8Error(RuntimeError):
    """Base class for toolkit errors."""
