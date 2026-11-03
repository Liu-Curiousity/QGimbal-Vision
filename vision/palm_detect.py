from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import mediapipe as mp
import numpy as np


@dataclass(frozen=True)
class DetectedPalm:
    """A detected palm in image coordinates."""

    center: Tuple[float, float]
    box: np.ndarray
    area: float


class PalmDetector:
    """Reuse MediaPipe Hands across frames and track the palm center."""

    def __init__(self) -> None:
        self._hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=2,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def detect(self, frame: np.ndarray) -> List[DetectedPalm]:
        results = self._hands.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        h, w = frame.shape[:2]
        palms = []
        for landmarks in results.multi_hand_landmarks or []:
            # 手腕和四指指根定义掌部，避免手指伸屈影响掌心位置。
            points = np.array([
                (landmarks.landmark[i].x * w, landmarks.landmark[i].y * h)
                for i in (0, 5, 9, 13, 17)
            ], dtype=np.float32)
            box = cv2.convexHull(points).reshape(-1, 2)
            center = points.mean(axis=0)
            palms.append(DetectedPalm(
                center=(float(center[0]), float(center[1])),
                box=box,
                area=float(cv2.contourArea(box)),
            ))
        # 沿用最大目标优先的选择方式。
        palms.sort(key=lambda palm: palm.area, reverse=True)
        return palms

    def close(self) -> None:
        self._hands.close()


def draw_detected_palm(
    frame: np.ndarray,
    palm: Optional[DetectedPalm],
    color: Tuple[int, int, int] = (0, 255, 0),
    thickness: int = 3,
    draw_center: bool = True,
    draw_text: bool = True,
) -> None:
    """Draw the palm outline and center in-place on a BGR frame."""
    if palm is None:
        return

    box = palm.box.astype(np.int32)
    cv2.polylines(frame, [box], isClosed=True, color=color, thickness=thickness)

    cx, cy = palm.center

    if draw_text:
        label = f"A:{int(palm.area)}"
        label_coord = f"X:{int(cx)} Y:{int(cy)}"
        cv2.putText(
            frame,
            label,
            (int(cx) - 80, int(cy) - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )
        cv2.putText(
            frame,
            label_coord,
            (int(cx) - 80, int(cy) + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
        )

    if draw_center:
        cv2.circle(frame, (int(cx), int(cy)), 5, (0, 0, 255), -1)
