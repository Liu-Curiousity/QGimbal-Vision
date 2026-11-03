from __future__ import annotations

import time

from typing import Tuple

import cv2
from vision.palm_detect import draw_detected_palm


def get_fps():
    if not hasattr(get_fps, "prev_time"):
        get_fps.prev_time = time.time()
        return 0.0
    if not hasattr(get_fps, "fps"):
        get_fps.fps = 0
        return 0.0
    now = time.time()
    dt = now - get_fps.prev_time
    get_fps.prev_time = now
    if dt > 0:
        alpha = 0.95
        inst_fps = 1.0 / max(dt, 1e-6)
        get_fps.fps = alpha * get_fps.fps + (1 - alpha) * inst_fps if get_fps.fps > 0 else inst_fps
    return get_fps.fps


class Feedbacker:
    """Feedbacker interface for gimbal control."""

    def __init__(self, display: bool) -> None:
        self.display = display
        self._last_print = time.time()
        self._window_name = "Camera"
        if self.display:
            cv2.namedWindow(self._window_name, cv2.WINDOW_NORMAL)

    def __del__(self):
        if self.display:
            cv2.destroyWindow(self._window_name)

    def close(self):
        self.__del__()

    def update(self, frame, palm,
               center_pixel: Tuple[int, int],
               error_pixel: Tuple[float, float],
               yaw_pitch_rpm: Tuple[float, float] | None
               ) -> None:
        fps = get_fps()
        err_x, err_y = error_pixel
        yaw_rpm, pitch_rpm = yaw_pitch_rpm if yaw_pitch_rpm is not None else (0.0, 0.0)
        if self.display:
            if palm is not None:
                draw_detected_palm(frame, palm)
            # 画面中心点
            cv2.drawMarker(frame, center_pixel, (255, 0, 0),
                           markerType=cv2.MARKER_CROSS, markerSize=18, thickness=2)
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            cv2.putText(
                frame,
                f"err(px)=({err_x:.0f},{err_y:.0f}) rpm=({yaw_rpm:.1f},{pitch_rpm:.1f})",
                (10, 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )
            cv2.imshow(self._window_name, frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("退出程序...")
                exit(0)
        else:
            # 无窗口：终端输出 FPS + 检测结果
            if (time.time() - self._last_print) >= 0.05:
                self._last_print = time.time()
                if palm is None:
                    print(f"fps={fps:.1f} palm=none rpm=({yaw_rpm:.1f},{pitch_rpm:.1f})")
                else:
                    cx, cy = palm.center
                    print(
                        f"fps={fps:.1f} cx={cx:.1f} cy={cy:.1f} area={palm.area:.0f} "
                        f"err=({err_x:.0f},{err_y:.0f}) rpm=({yaw_rpm:.1f},{pitch_rpm:.1f})"
                    )
