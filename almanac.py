from datetime import datetime

from .moon_phase import moon_phase
from .riseset import BODIES, day_riseset

TWILIGHT = {"民用": -6.0, "航海": -12.0, "天文": -18.0}
PLANETS = ("MERCURY", "VENUS", "MARS", "JUPITER","SATURN", "URANUS", "NEPTUNE")

def _twilight_line(name, h0, r):
    """输出单级曙暮光；分别处理完整、仅有一个和全天无跨越事件。"""
    rise = r["rise_time"]
    set_ = r["set_time"]
    if rise is not None and set_ is not None:
        return f"{name}晨光始 {rise}，{name}昏影终 {set_}；"
    if rise is not None:
        return f"{name}晨光始 {rise}，当日无{name}昏影终；"
    if set_ is not None:
        return f"当日无{name}晨光始，{name}昏影终 {set_}；"

    # 无跨越事件时，用当日上中天高度区分全天高于或低于阈值。
    transit_high = r["transit_high"]
    if transit_high is not None and float(transit_high.removesuffix("°")) > h0:
        return f"无{name}夜（太阳终日高于 {h0}°）；"
    return f"全天处于{name}夜；"

def _planet_line(name, r):
    """
    输出为单个行星的报告文本。r为单次计算结果。
    """
    if r["transit_time"] is  None:
        return f"{name}：该行星整日在地平线下；"
    if r["set_time"] is  None:
        return f"{name}：该行星整日在地平线上，中天时间 {r['transit_time']}，中天高度 {r['transit_high']}；"
    return f"{name}：升起时间 {r['rise_time']}，落下时间 {r['set_time']}，中天时间 {r['transit_time']}，中天高度 {r['transit_high']}；"

def wrapper(t: datetime, lat, lon):
    """
    三级蒙影时间计算，输入为datetime与观测地经纬度，输出为报告文本。
    """
    sun_pos = BODIES["SUN"][0]
    lines = [_twilight_line(name, h0, day_riseset(sun_pos, lat, lon, h0, t)) for name, h0 in TWILIGHT.items()]

    return "\n".join(lines)

def today_summary(lat, lon):
    """
    输出指定经纬度的当日综合天文信息。
    """
    # today 取今天北京 naive 零点：datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_moon = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)   

    # 太阳段：day_riseset(BODIES["SUN"][0], lat, lon, SUN_H0, today)  → 日出日落中天
    dict_sun = day_riseset(BODIES["SUN"][0], lat, lon, BODIES["SUN"][1], today)

    if dict_sun["transit_time"] is None:
        result_sun = "今日太阳不升起，为极夜；\n"
    elif dict_sun["set_time"] is None:
        result_sun = (f"今日太阳不落下，为极昼；\n"
                      f"中天时间 {dict_sun['transit_time']}，中天高度 {dict_sun['transit_high']}；\n")
    else:
        result_sun = (f"今日太阳升起时间 {dict_sun['rise_time']}，落下时间 {dict_sun['set_time']}；\n"
                      f"中天时间 {dict_sun['transit_time']}，中天高度 {dict_sun['transit_high']}；\n")

    # 蒙影段：wrapper(day, lat, lon)
    result_wrapper = wrapper(today, lat, lon)

    # 月亮段：day_riseset(day, lat, lon, BODIES["MOON"][0], MOON_H0) + 月相
    dict_moon = day_riseset(BODIES["MOON"][0], lat, lon, BODIES["MOON"][1], today)

    if dict_moon["transit_time"] is None:
        result_moon = "今日月亮不升起；\n"
    elif dict_moon["set_time"] is None:
        result_moon = (f"今日月亮不落下；\n"
                       f"中天时间 {dict_moon['transit_time']}，中天高度 {dict_moon['transit_high']}；\n")
    else:
        result_moon = (f"今日月亮升起时间 {dict_moon['rise_time']}，落下时间 {dict_moon['set_time']}；\n"
                       f"中天时间 {dict_moon['transit_time']}，中天高度 {dict_moon['transit_high']}；\n")

    phase = moon_phase(today_moon)
    result_phase = f"月相 {phase['phase_name']}，月面照明率 {phase['illumination']}；\n"

    # 行星段：for name, (pos_fn, h0) in BODIES.items()，跳过 SUN/MOON，逐颗 day_riseset

    planet_list = []
    for name in PLANETS:
        pos_fn, h0 = BODIES[name]
        r = day_riseset(pos_fn, lat, lon, h0, today)
        one_result = _planet_line(name, r)
        planet_list.append(one_result)

    result_planet = "\n".join(planet_list)

    # return 拼好的字符串
    result_list = [result_sun, result_wrapper, result_moon, result_phase, result_planet]
    result = "\n".join(result_list)

    return result