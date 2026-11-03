import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Tuple


@dataclass()
class GimbalSerialStub:
    port: str
    baudrate: int

    class CmdType(IntEnum):
        NOP = 0x00,  # 无操作
        Enable = 0x01,  # 使能
        Disable = 0x02,  # 失能
        CurrentCtrl = 0x03,  # 电流控制
        SpeedCtrl = 0x04,  # 速度控制
        AngleCtrl = 0x05,  # 角度控制
        LowSpeedCtrl = 0x06,  # 低速控制
        StepAngleCtrl = 0x07,  # 角度递增控制

        EnableStability = 0xFF,  # 使能自稳
        DisableStability = 0xFE,  # 失能自稳
        EnableLaser = 0xFD,  # 使能激光
        DisableLaser = 0xFC,  # 失能激光
        ResetIMU = 0xFB,  # 复位IMU(角度调零)

    def __post_init__(self) -> None:
        self.enabled = False
        self.laser_enabled = False
        self.stability_enabled = False
        self.imu_speed = 0, 0  # speed yaw, pitch in RPM
        self.imu_angle = 0, 0  # angle yaw, pitch in rad
        self.current = 0, 0  # current yaw, pitch in A
        self.speed = 0, 0  # speed yaw, pitch in RPM
        self.angle = 0, 0  # angle yaw, pitch in rad
        self._ser = None

    def open(self) -> None:
        if self.port is None:
            return
        import serial
        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=0,
            write_timeout=0.01,
        )

    def close(self) -> None:
        if self._ser is None:
            return
        self.send_command(self.CmdType.Disable)
        self._ser.close()
        self._ser = None

    def __del__(self):
        self.close()

    def send_command(self, cmd_type: CmdType, data: Tuple[float, float] = (0.0, 0.0)) -> None:
        if self._ser is None:
            return
        pkt = struct.pack("<Bff", cmd_type, *data)
        pkt = pkt + struct.pack("<B", crc8(pkt, polynomial=0x07, init=0x00, xor_out=0x00))
        self._ser.write(pkt)
        data = self._ser.read(42)
        if len(data) == 42 and data[41] == crc8(data[:41], polynomial=0x07, init=0x00, xor_out=0x00):
            # 解析数据
            values = struct.unpack("<BffffffffffB", data)
            state = values[0]
            self.enabled = bool(state & 0x01)
            self.stability_enabled = bool(state & 0x02)
            self.laser_enabled = bool(state & 0x04)
            self.imu_speed = values[1:3]
            self.imu_angle = values[3:5]
            self.angle = values[5:7]
            self.speed = values[7:9]
            self.current = values[9:11]
            return
        else:
            print(f"串口数据长度错误或 CRC 校验失败，收到 {len(data)} 字节数据: {data.hex()}")


def reverse_bits(data: int) -> int:
    """反转一个字节的 bit 顺序"""
    data &= 0xFF
    data = ((data & 0x55) << 1) | ((data & 0xAA) >> 1)
    data = ((data & 0x33) << 2) | ((data & 0xCC) >> 2)
    data = ((data & 0x0F) << 4) | ((data & 0xF0) >> 4)
    return data & 0xFF


def crc8(
        data: bytes | bytearray,
        polynomial: int,
        init: int,
        xor_out: int,
        input_invert: bool = False,
        output_invert: bool = False,
) -> int:
    """
    通用 CRC-8 计算

    Args:
        data: 输入数据
        polynomial: CRC 多项式（例如 0x07）
        init: 初始值
        xor_out: 最终异或值
        input_invert: 是否按 bit 反转每个输入字节
        output_invert: 是否按 bit 反转最终 CRC

    Returns:
        CRC8 值（0~255）
    """
    if not data:
        raise ValueError("data must not be empty")

    crc = init & 0xFF

    for byte in data:
        if input_invert:
            byte = reverse_bits(byte)

        crc ^= byte

        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ polynomial) & 0xFF
            else:
                crc = (crc << 1) & 0xFF

    crc ^= xor_out
    crc &= 0xFF

    if output_invert:
        crc = reverse_bits(crc)

    return crc
