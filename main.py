# 摄像头读取并显示画面
# 使用: python main.py --camera 0

"""
简单的摄像头预览脚本（使用 OpenCV）。
参数：
  --camera        摄像头索引（默认 0）
  --display       是否显示图形化窗口（0/1，默认 1）
                 - 1：显示图像（现有效果），并叠加手掌与 FPS
                 - 0：不显示窗口，在终端输出 FPS + 检测到的掌心坐标/面积
  --print-interval 终端输出间隔秒数（仅 --display 0 时生效，默认 0.5）

GUI 模式按 'q' 或 ESC 退出；无窗口模式请按 Ctrl+C 退出。
"""

import argparse
import time
import sys

import cv2

from vision.palm_detect import PalmDetector

from control.pid import PID
from control.feedbacker import Feedbacker
from control.serial_stub import GimbalSerialStub
from control.tracker_control import GimbalTracker

DEFAULT_CAMERA = 0  # 摄像头索引（默认 0）
DEFAULT_WIDTH = 640  # 期望宽度
DEFAULT_HEIGHT = 480  # 期望高度
DEFAULT_FPS = 120  # 期望帧率
DEFAULT_DISPLAY = 1

# 控制默认参数（可通过命令行覆盖）
DEFAULT_MAX_RPM = 20.0
DEFAULT_LOST_TIMEOUT_S = 0.4


def parse_args():
    p = argparse.ArgumentParser(description="OpenCV 摄像头显示示例")
    p.add_argument('--camera', type=int, default=DEFAULT_CAMERA, help=f'摄像头索引（默认 {DEFAULT_CAMERA}）')
    p.add_argument('--display', type=int, choices=[0, 1], default=DEFAULT_DISPLAY,
                   help=f'是否显示图形化窗口（0/1，默认 {DEFAULT_DISPLAY}）')

    # 控制相关
    p.add_argument('--max-rpm', type=float, default=DEFAULT_MAX_RPM,
                   help=f'最大转速输出（RPM，默认 {DEFAULT_MAX_RPM}）')
    p.add_argument('--lost-timeout', type=float, default=DEFAULT_LOST_TIMEOUT_S,
                   help=f'丢目标超时后复位控制器的时间（秒，默认 {DEFAULT_LOST_TIMEOUT_S}）')
    p.add_argument('--serial-port', type=str, default=None, help='串口端口号，例如 COM3；不填则不发送')
    p.add_argument('--serial-baud', type=int, default=115200, help='串口波特率（默认 115200）')

    return p.parse_args()


def main():
    args = parse_args()

    # 根据系统环境选择后端
    if sys.platform.startswith('linux'):
        cap = cv2.VideoCapture(args.camera, cv2.CAP_V4L2)
    elif sys.platform.startswith('win'):
        cap = cv2.VideoCapture(args.camera, cv2.CAP_MSMF)
    else:
        cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        print(f"无法打开摄像头索引 {args.camera}. 请检查设备或更换索引。")
        sys.exit(2)

    # 设置参数
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')) # 设置为 MJPG 格式
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, DEFAULT_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, DEFAULT_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, DEFAULT_FPS)
    print(f"info: capture backend: {cap.getBackendName()}")
    print(f"info: capture resolution: {cap.get(cv2.CAP_PROP_FRAME_WIDTH)}x{cap.get(cv2.CAP_PROP_FRAME_HEIGHT)}")
    print(f"info: capture FPS: {cap.get(cv2.CAP_PROP_FPS)}")

    # 控制器初始化
    tracker = GimbalTracker(
        yaw_pid=PID(kp=150.0, ki=60.0, kd=1.4, integral_limit=0.15, output_limit=args.max_rpm),
        pitch_pid=PID(kp=100.0, ki=40.0, kd=1.4, integral_limit=0.15, output_limit=args.max_rpm),
        lost_timeout_s=args.lost_timeout, invert_yaw=True
    )
    serial_stub = GimbalSerialStub(args.serial_port, args.serial_baud)
    feedbacker = Feedbacker(display=args.display)
    palm_detector = PalmDetector()
    serial_stub.open()

    tracker.enabled = True
    serial_stub.send_command(serial_stub.CmdType.EnableLaser)  # 启用激光
    serial_stub.send_command(serial_stub.CmdType.EnableStability)  # 启用陀螺仪稳定
    serial_stub.send_command(serial_stub.CmdType.Enable)  # 启用云台
    try:
        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                print("无法从摄像头读取到帧，正在重试...")
                time.sleep(0.1)
                continue

            frame = cv2.flip(frame, -1)  # 翻转画面

            # 对每帧执行手掌检测
            palms = palm_detector.detect(frame)
            best_palm = palms[0] if palms else None
            best_palm_center = best_palm.center if best_palm else None

            # PID 控制：将目标中心追踪到屏幕中心，输出 yaw/pitch rpm
            tracker.target_center = (frame.shape[:2][1] // 2 + 10, frame.shape[:2][0] // 2)  # 追踪目标, 单位: px
            error_pixel, yaw_pitch_rpm = tracker.update(frame.shape[:2], best_palm_center)
            if yaw_pitch_rpm is not None:
                yaw_rpm, pitch_rpm = yaw_pitch_rpm
                serial_stub.send_command(serial_stub.CmdType.SpeedCtrl, (yaw_rpm, pitch_rpm))  # 发送转速到云台

            feedbacker.update(frame, best_palm, tracker.target_center, error_pixel, yaw_pitch_rpm)

    except KeyboardInterrupt:
        print('\n收到中断，退出...')
    finally:
        cap.release()
        serial_stub.close()
        feedbacker.close()
        palm_detector.close()


if __name__ == '__main__':
    main()
