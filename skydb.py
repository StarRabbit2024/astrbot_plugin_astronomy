"""天体数据库：星表查询 + 今晚推荐 + BODIES 注册"""
import json
import math
from datetime import datetime, timedelta
from pathlib import Path

from .moon_phase import moon_phase
from .riseset import STAR_H0, d_j2000, BODIES, day_riseset, moon_pos, normalize_body_name

# ---------- 1. 加载与索引（模块级，导入即建好） ----------
_CATALOG = json.loads((Path(__file__).parent / "DSO_database.json").read_text(encoding="utf-8"))["objects"]
# 别名反查表：规范化别名 → 条目 dict
_ALIAS2OBJ = {}
for _o in _CATALOG:
    for _a in [_o["name"]] + _o["aliases"]:
        _ALIAS2OBJ[normalize_body_name(_a)] = _o

def _lookup_entry(name):
    """name → 星表条目 dict，未收录返回 None。"""
    key = normalize_body_name(name)
    if not key:
        return None
    return _ALIAS2OBJ.get(key)

# ---------- 2. 岁差修正（低精度速率法） ----------
def _precess(ra_h: float, dec_d: float, t: datetime):
    """J2000 坐标修正到 t 时刻（naive UTC）。
    公式（每年）：ΔRA = (3.07496 + 1.33621·sinRA·tanDec) 秒时间
                  ΔDec = 20.0431·cosRA 角秒
    T = 儒略年数（t 距 J2000.0 的年数，可带小数）
    返回 (修正后 ra小时, dec度)。注意 sin/cos/tan 全用弧度。
    """
    ra_rad = math.radians(ra_h*15)
    dec_rad = math.radians(dec_d)

    d_ra = (3.07496 + 1.33621*math.sin(ra_rad)*math.tan(dec_rad))
    d_dec = 20.0431*math.cos(ra_rad)

    T = d_j2000(t)/365.25
    d_ra = (T*d_ra)/3600
    d_dec = (T*d_dec)/3600

    return (ra_h+d_ra, dec_d+d_dec)

# ---------- 3. 静态位置函数工厂（给升落引擎用） ----------
def _make_pos(ra_h, dec_d):
    """闭包陷阱老朋友：默认参数捕获。引擎要 pos_fn(t) → (ra小时, dec度)。"""
    def pos(t, ra_h=ra_h, dec_d=dec_d):
        return _precess(ra_h, dec_d, t)
    return pos

def register_bodies(bodies):
    """把每个深空天体的中文名和全部别名注册到 riseset 的 BODIES。"""
    for obj in _CATALOG:
        pos = _make_pos(obj["ra"], obj["dec"])
        for alias in [obj["name"], *obj["aliases"]]:
            bodies[normalize_body_name(alias)] = (pos, STAR_H0)

# ---------- 4. 点查 ----------
def query_celestial(name, lat=31, lon=118):
    """name 接受中文名/M/NGC/IC/英文别名。
    命中：返回中文信息串（名称、类型、星座、星等、角大小、备注）。
    未命中：返回教学文本（列类别不列名）——这条错误信息就是 API 的一部分。
    查别名表前先 strip，ASCII 别名 upper 后再查。
    """
    obj = _lookup_entry(name)
    if obj is None:
        shown = name.strip() if isinstance(name, str) else ""
        return (f"未收录天体「{shown}」。目前支持：太阳、月亮、八大行星、"
                "全部梅西耶天体（M1~M110）及部分著名深空天体"
                "（如玫瑰星云、北美洲星云），可用中文名、M 编号或 NGC/IC 编号查询。")

    name_real = obj["name"]

    t = datetime.now()
    body_key = normalize_body_name(name_real)
    rt = day_riseset(BODIES[body_key][0], lat, lon, BODIES[body_key][1], t)

    mag = obj.get("mag")           # 星等
    obj_type = obj.get("type")     # 类型
    const = obj.get("const")       # 星座
    size = obj.get("size")         # 视大小

    data = [mag, obj_type, const, size]
    data = ["无数据" if i is None else i for i in data]

    result = (f"天体「{name_real}」基本信息：\n"
                f"星等：{data[0]}，天体类型：{data[1]}，所属星座：{data[2]}，视大小 {data[3]}\n"
                f"今日中天时间：{rt['transit_time']}，中天高度：{rt['transit_high']}，升起时间：{rt['rise_time']}，落下时间：{rt['set_time']}")

    return result

# ---------- 5. 今晚推荐 ----------
def tonight_targets(lat, lon, top=5, night_start=21, night_end=3):
    """推荐今夜目标；避月惩罚同时考虑中天月距和月面照明率，不使用月球高度角。"""
    _obj = []
    obj = []
    t = datetime.now()

    for i in _CATALOG:
        if i["mag"] is None:
            continue
        elif i["mag"] <= 8:
            _obj.append(i)

    for i_raw in _obj:
        i = dict(i_raw)
        name = i["name"]
        body_key = normalize_body_name(name)
        pos_dso = BODIES[body_key][0]
        dso_h0 = BODIES[body_key][1]

        r_i = day_riseset(pos_dso, lat, lon, dso_h0, t)
        if r_i["transit_time"] is None:
            continue

        tt = datetime.strptime(r_i["transit_time"], "%H:%M")
        day = t if tt.hour >= 12 else t + timedelta(days=1)
        transit_dt = day.replace(hour=tt.hour, minute=tt.minute, second=0, microsecond=0)
        h = transit_dt.hour + transit_dt.minute/60

        if not (h >= night_start or h <= night_end):
            continue

        if i["mag"] <= 1:
            score_m = 1
        else:
            score_m = 1 - 0.1*i["mag"]      # 星等分

        transit_high = float(r_i["transit_high"].replace("°", ""))
        score_h = transit_high/90    # 高度分

        score = score_h*0.5 + score_m*0.5

        ra_dso, dec_dso = pos_dso(transit_dt - timedelta(hours=8))
        ra_moon, dec_moon = moon_pos(transit_dt - timedelta(hours=8))

        d_ra = math.radians((ra_dso - ra_moon) * 15)
        d1 = math.radians(dec_dso)
        d2 = math.radians(dec_moon)
        cos_d = math.sin(d1)*math.sin(d2) + math.cos(d1)*math.cos(d2)*math.cos(d_ra)
        moon_sep = math.degrees(math.acos(max(-1.0, min(1.0, cos_d))))
        illumination = float(moon_phase(transit_dt)["illumination"].rstrip("%")) / 100.0

        # 满月时保留原惩罚，新月时无惩罚，中间随照明率线性变化。
        if moon_sep < 10:
            score *= 1.0 - 0.8*illumination
        elif moon_sep < 30:
            score *= 1.0 - 0.3*illumination

        i["score"] = score*100
        i["transit_high"] = r_i["transit_high"]
        i["transit_time"] = r_i["transit_time"]
        obj.append(i)

    obj.sort(key=lambda o: -o["score"])

    result = []
    result0 = f"今夜晚观测目标 Top {top}："
    result.append(result0)
    for i in range(min(top, len(obj))):
        win = obj[i]
        text = f"{i+1}. {win['name']} 编号：{win['aliases'][0]}（{win['type']}，{win['mag']}等） {win['transit_time']} 最高 {win['transit_high']}"
        result.append(text)

    return "\n".join(result)

# ---------- 7. 自测 ----------
if __name__ == "__main__":

    register_bodies(BODIES)
    print(query_celestial("M42"))
    print(query_celestial("玫瑰星云"))
    print(query_celestial("NGC 7000"))
    print(query_celestial("波德星系"))
    print(query_celestial("阿贝尔39"))      # 应走未收录教学文本
    print(tonight_targets(31.94, 118.79))