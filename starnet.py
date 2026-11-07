import json
import math
import time
from datetime import datetime, timedelta
from urllib.error import URLError
from urllib.request import urlopen

from .moon_phase import moon_phase
from .riseset import moon_pos

_cache = {}    # 晴天钟调用缓存
_TTL = 1800    # 缓存有效期 30 分钟，单位秒

_W_MOON, _W_TRANS, _W_SEEING = 5, 4, 3
_TRANS_NEUTRAL = 60.0                     # 云多时不采信透明度，给中性分
# 官方刻度翻译
_CLOUD_TXT = ["", "0~6%", "6~19%", "19~31%", "31~44%", "44~56%", "56~69%", "69~81%", "81~94%", "94~100%"]
_SEEING_TXT = ["", "<0.5″", "0.5~0.75″", "0.75~1″", "1~1.25″", "1.25~1.5″", "1.5~2″", "2~2.5″", ">2.5″"]
_TRANS_TXT = ["", "<0.3", "0.3~0.4", "0.4~0.5", "0.5~0.6", "0.6~0.7", "0.7~0.85", "0.85~1", ">1"]

def _rating(score: float) -> str:
    if score >= 90:
        return "极佳"
    if score >= 70:
        return "良好"
    if score >= 50:
        return "一般"
    if score >= 30:
        return "较差"
    return "极差"

def _gmst_deg(t_ut: datetime) -> float:
    """平恒星时（度），低精度够算月亮高度角用。"""
    d = (t_ut - datetime(2000, 1, 1, 12)).total_seconds()/86400.0
    return (280.46061837 + 360.98564736629*d)%360.0

def _moon_score(t_bj: datetime, lat: float, lon: float) -> float:
    """月光得分 0–100：照亮比例 × 高度角平方惩罚，越高越好。"""
    t_ut = t_bj - timedelta(hours=8)
    ra_h, dec = moon_pos(t_ut)
    ha = math.radians(_gmst_deg(t_ut) + lon - ra_h*15.0)

    alt = math.degrees(math.asin(math.sin(math.radians(lat))*math.sin(math.radians(dec)) + math.cos(math.radians(lat))*math.cos(math.radians(dec))*math.cos(ha)))

    illum_str = moon_phase(t_bj)["illumination"]
    illum = float(illum_str.rstrip("%")) / 100.0

    return 100.0*(1.0 - illum*max(0.0, alt/90.0)**2)

def _slot_score(s: dict, lat: float, lon: float) -> float:
    """综合打分"""
    cloud = (9 - s["cloudcover"]) * 12.5          # 0–100，门限因子
    if s["prec_type"] != "none":
        cloud = 0.0
    moon = _moon_score(s["timepoint"], lat, lon)
    if s["cloudcover"] <= 3:
        trans = (8 - s["transparency"]) / 7 * 100
    else:
        trans = _TRANS_NEUTRAL
    seeing = (8 - s["seeing"]) / 7 * 100
    # 三项归一加权成"净空质量"（0–100）
    quality = (
        _W_MOON * moon + _W_TRANS * trans + _W_SEEING * seeing
    ) / (_W_MOON + _W_TRANS + _W_SEEING)
    return cloud / 100.0 * quality

def _report(lat: float, lon: float, buckets: dict) -> str:
    now = datetime.now()
    today = now.date()
    plan = [(today, "晨", "今日凌晨"),
            (today, "夜", "今日夜晚"),
            (today + timedelta(days=1), "晨", "明日凌晨"),
            (today + timedelta(days=1), "夜", "明日夜晚")]
    lines = []
    for d, seg, name in plan:
        slots = [s for s in buckets.get((d, seg), []) 
                if s["timepoint"] > now
                and s["cloudcover"] != -9999
                and s["seeing"] != -9999
                and s["transparency"] != -9999]
        if not slots:
            continue                          # 段已过去或无有效数据，不出行

        avg = sum(_slot_score(s, lat, lon) for s in slots) / len(slots)

        lines.append(f"{name}：{avg:.0f}分（{_rating(avg)}）")

    if not lines:
        return "未来 48 小时内没有可用的预报数据。"
    return "\n".join(lines)

def _cache_get(lat, lon):
    """
    缓存读取与检查。
    """
    key = (round(lat, 2), round(lon, 2))
    hit = _cache.get(key)      # key 不存在时返 None，不抛 KeyError
    if hit is None:
        return None            # 没缓存过
    ts, data = hit
    if time.monotonic() - ts > _TTL:
        return None            # 过期了
    return data

def _cache_put(lat, lon, data):
    """
    缓存写入。
    """
    key = (round(lat, 2), round(lon, 2))
    _cache[key] = (time.monotonic(), data)

def _fetch_raw(lat, lon):
    """缓存检查→拉取→校验→写缓存。返回原始 dict 或 None。"""
    # ① 缓存检查：模块级 _cache = {}，key=(round(lat,2), round(lon,2))，
    #    value=(time.monotonic(), data)；半小时内直接返回旧数据
    data = _cache_get(lat, lon)

    # ② 拼 URL："https://www.7timer.info/bin/api.pl?" + urlencode({...})
    # ③ 拉取：try 里 urlopen(url, timeout=10).read()
    # ④ 解析：json.loads → data
    if data is None:
        url = f"https://www.7timer.info/bin/api.pl?lon={lon}&lat={lat}&product=astro&output=json"
        try:
            raw_data = urlopen(url, timeout=10).read()
            data = json.loads(raw_data)
        except (URLError, TimeoutError, OSError, ValueError):
            return None
        
    # ⑤ 基本校验：data 里有 "init" 和 "dataseries" 才算数，否则 None
        if "init" not in data or "dataseries" not in data:
            return None
    # ⑥ 写缓存
        _cache_put(lat, lon, data)

    return data



def fetch_astro(lat, lon):
    """
    URL拉取晴天钟json数据，简化整理，并生成观星指数。
    """
    data = _fetch_raw(lat, lon)

    if data is None:
        return "与晴天钟的链接出现问题！天文预报获取失败。"

    # 两条路汇合后统一转换
    init = data["init"]
    dataseries = data["dataseries"]
    for i in dataseries:
        i["timepoint"] = datetime.strptime(init, "%Y%m%d%H") + timedelta(hours=8 + i["timepoint"])


    buckets = {}                       # key: (date, "夜"/"晨") → 槽列表
    for i in dataseries:
        t = i["timepoint"]             # 你已转好的北京 datetime
        h = t.hour
        if 16 <= h <= 23:
            key = (t.date(), "夜")     # 槽起始 17,20,23 → 夜晚段
        elif 0 <= h <= 9:
            key = (t.date(), "晨")     # 槽起始 2,5,8 → 凌晨段
        else:
            continue                   # 11/14 槽直接扔
        buckets.setdefault(key, []).append(i)

    return _report(lat, lon, buckets)

def fetch_llm_astro(lat, lon):
    """
    URL拉取晴天钟json数据，简化整理，转化为提供给LLM的字符串。
    """
    data = _fetch_raw(lat, lon)
    if data is None:
        return "与晴天钟的链接出现问题！天文预报获取失败。"    
    lines = []
    for i in data["dataseries"]:
        t = datetime.strptime(data["init"], "%Y%m%d%H") + timedelta(hours=8 + i["timepoint"])
        if not (17 <= t.hour <= 23 or 0 <= t.hour <= 8):
            continue  # 白天和黄昏槽不要
        lines.append(
            f"{t.month}月{t.day}日{t.hour}时："
            f"云量{_CLOUD_TXT[i['cloudcover']]}，"
            f"视宁度{_SEEING_TXT[i['seeing']]}，"
            f"透明度{_TRANS_TXT[i['transparency']]}，"
            f"湿度{(i['rh2m'] + 4.5) * 5:.0f}%，"
            f"降水：{i['prec_type']}，气温{i['temp2m']}℃"
            )
    return "以下为未来3天逐时段天文预报（北京时间）：\n" + "\n".join(lines)      