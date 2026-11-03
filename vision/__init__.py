"""Vision modules for this project.

This package contains small, reusable computer vision utilities used by `main.py`.
"""

from .palm_detect import DetectedPalm, PalmDetector, draw_detected_palm

__all__ = [
    "DetectedPalm",
    "PalmDetector",
    "draw_detected_palm",
]
