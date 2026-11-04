import math
from datetime import UTC, datetime, timedelta, timezone

CN = timezone(timedelta(hours=8))
PHASES = ["新月", "娥眉月", "上弦月", "盈凸月", "满月", "亏凸月", "下弦月", "残月"]
SYNODIC = 29.530589  # 月龄周期
standard_date = datetime(
    2000, 1, 6, 18, 14, tzinfo=UTC
)  # 标准位置，此时月相为新月，age为0


def normalize(dt: datetime) -> datetime:
    """
    输入: 一个 datetime（带时区信息最佳，不带就当CN东八区）
    返回: 一个 datetime UTC时区
    """
    if dt.tzinfo is None:  # 判断：不带时区
        dt = dt.replace(tzinfo=CN)  # 贴上东八区标签
    return dt.astimezone(UTC)  # 统一换算成 UTC 再算


def moon_phase(time_data: datetime) -> dict:
    """
    输入: 一个 datetime（带时区信息最佳，不带就当CN东八区）
    返回: {
        "age": 月相年龄(天, 0~29.53)字符串,
        "illumination": 照亮比例(0%~100%)字符串,
        "phase_name": "盈凸月" 等中文八相名
    }
    """
    time_data = normalize(time_data)  # 与标准位置计算时间差
    delta_time = time_data - standard_date
    diff_days = delta_time.total_seconds() / 86400.0

    age = diff_days % SYNODIC

    phase = (age / SYNODIC) * 2 * math.pi
    illumination = (1 - math.cos(phase)) / 2

    step = SYNODIC / 8  # 每段宽度 3.6913
    index = int(age / step) % 8  # 落在第几段
    phase_name = PHASES[index]

    data_dict = {
        "age": f"{age:.2f}",
        "illumination": f"{illumination * 100:.1f}%",
        "phase_name": phase_name,
    }
    return data_dict


if __name__ == "__main__":
    print(moon_phase(datetime.now()))
