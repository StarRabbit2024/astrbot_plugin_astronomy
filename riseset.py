import math
from datetime import datetime, timedelta

SUN_H0 = -0.833
STAR_H0 = -0.567

def d_j2000(dt: datetime): 
    """
        datetime(UTC) → 距 J2000.0 的天数
    """
    dj = dt.toordinal() - 730120.5 + (dt.hour*3600 + dt.minute*60 + dt.second) / 86400
    return dj

def gmst0(base: datetime):
    """base(0h UT) → 格林尼治平恒星时(度)"""
    Tu = d_j2000(base) / 36525
    return (100.46061837 + 36000.770053608*Tu
            + 0.000387933*Tu**2 - Tu**3/38710000) % 360

def wrap180(x): return (x + 180) % 360 - 180

def delta_t_seconds(year_float):
    """UT 与力学时之差（秒）。year_float 为带小数的年份，如 2026.84"""
    u = year_float - 2000.0
    return 62.92 + 0.32217*u + 0.005589*u**2

def sun_pos(t: datetime):
    """
    计算目标时间太阳在天球上的坐标。
    输入: 一个 datetime UTC
    返回: (赤经(小时), 赤纬(度))
    """
    n = d_j2000(t)
    M = (357.5291 + 0.98560028*n) % 360                                                 # 平近点角
    M_rad = math.radians(M)
    C = 1.9148*math.sin(M_rad) + 0.0200*math.sin(2*M_rad) + 0.0003*math.sin(3*M_rad)    # 中心差
    λ = (M + C + 180 + 102.9372) % 360                                                  # 黄经
    λ_rad = math.radians(λ)
    Dec = math.asin(math.sin(λ_rad)*math.sin(math.radians(23.4397)))                    # 赤纬
    RA = math.atan2(math.cos(math.radians(23.4397))*math.sin(λ_rad), math.cos(λ_rad))   # 赤经

    dec_deg = math.degrees(Dec)
    ra_hours = math.degrees(RA) / 15 % 24
    
    return (ra_hours, dec_deg)

def _refine(m, kind, ctx: dict):                    
    """
    迭代确定更佳的m。
    输入:近似的m, kind: 计算类型"rise"/"set"/"transit", 参数字典ctx
    """
    for _ in range(2):                   # 固定 2 轮迭代
        n   = m + ctx["d_T"]/86400
        ra  = ctx["ra0"] + ctx["d_ra"] * n                     # 小时
        dec = ctx["dec0"] + ctx["d_dec"] * n                   # 度
        θ   = (ctx["theta0"] + 360.985647 * m) % 360       # 度，注意乘的是 m 不是 n
        H   = wrap180(θ - ctx["lon"] - ra * 15)         # 度

        dec_rad = math.radians(dec)
        H_rad = math.radians(H)

        h_rad =math.asin(math.sin(ctx["lat_rad"])*math.sin(dec_rad) + math.cos(ctx["lat_rad"])*math.cos(dec_rad)*math.cos(H_rad))   # 此刻高度,弧度
        h = math.degrees(h_rad)                 # 此刻高度,度
            
        if kind == "transit":
            m += -H / 360
        else:
            m += (h - ctx["h0"]) / (360*math.cos(ctx["lat_rad"])*math.cos(dec_rad)*math.sin(H_rad))
    return m

def _events_on_base(base, pos_fn, lat, lon_east, h0, d_T):
    """
        收集单个日期内的升落事件，单个base → [(kind, m)]
    """
    lon = -lon_east
    theta0 = gmst0(base)
    lat_rad = math.radians(lat)
    ra0, dec0 = pos_fn(base)
    ra1, dec1 = pos_fn(base + timedelta(days=1))
    d_ra = (ra1 - ra0) % 24     # 小时/天
    d_dec = dec1 - dec0         # 度/天

    m0 = ((ra0*15 - theta0 + lon) / 360) % 1

    ctx = {"lat": lat, "lon": lon, "h0": h0, "ra0": ra0, "dec0": dec0,"d_ra": d_ra, "d_dec": d_dec, "theta0": theta0, "d_T": d_T, "lat_rad": lat_rad}

    dec0_rad = math.radians(dec0)
    h0_rad = math.radians(h0)
    cos_h0 = ((math.sin(h0_rad) - math.sin(lat_rad)*math.sin(dec0_rad))/(math.cos(lat_rad)*math.cos(dec0_rad)))

    if cos_h0 >= 1:                       # 拱极：永不落，只有中天
        m = _refine(m0, "transit", ctx)
        dec_t = dec0 + d_dec*(m + d_T/86400)
        h = 90 - abs(lat - dec_t)
        return [("transit_time", [m, h])]
    if cos_h0 <= -1:                      # 永不升
        return []

    H0 = math.degrees(math.acos(cos_h0))
    m = _refine(m0, "transit", ctx)
    dec_t = dec0 + d_dec*(m + d_T/86400)
    h = 90 - abs(lat - dec_t)

    return [("rise_time", _refine(m0 - H0/360, "rise", ctx)),
            ("transit_time", [m, h]),
            ("set_time", _refine(m0 + H0/360, "set", ctx))]

def _collect_events(pos_fn, lat, lon_east, h0, base_list):
    """
        收集指定时间内的升落事件，若干 base → [(kind, 北京时间datetime)]
    """
    out = []
    for base in base_list:
        dT = delta_t_seconds(2000 + d_j2000(base)/365.25)
        for kind, m in _events_on_base(base, pos_fn, lat, lon_east, h0, dT):
            if kind == "transit_time":
                t_utc = base + timedelta(days=m[0])
                t_cn = t_utc + timedelta(hours=8)
                out.append((kind, [t_cn, m[1]]))
            else:
                t_utc = base + timedelta(days=m)
                out.append((kind, t_utc + timedelta(hours=8)))
    return out

# ---------- 模式一：日历查询 ----------

def day_riseset(pos_fn, lat, lon_east, h0, date_local):
    """    
    计算目标天体在单日的升落时间，默认使用北京时间。
    输入: 
        pos_fn:用于计算天体在天球上的坐标的函数,
        lat, lon_east:观测地点经纬度,
        h0:几何高度阈值，大气折射，视半径，视差的修正,
        date_local:北京时间的日期
    输出：{
        "date_local":北京时间的日期,
        "rise_time":升起时间,
        "transit_time":中天时间,
        "transit_high":中天高度,
        "set_time":落下时间
        }
    """
    day = date_local.replace(hour=0, minute=0, second=0, microsecond=0)
    base_z = day - timedelta(days=1)
    events = _collect_events(pos_fn, lat, lon_east, h0, [base_z, day])
    result = {"date_local": day.date().isoformat(), "rise_time": None, "transit_time": None, "set_time": None, "transit_high": None}
    for kind, t_cn in events:
        if kind == "transit_time":
            result[kind] = t_cn[0].strftime("%H:%M")
            h = t_cn[1]
            result["transit_high"] = f"{h:.1f}°"
        else:
            if t_cn.date() == day.date():
                result[kind] = t_cn.strftime("%H:%M")
    return result

# ---------- 模式二：此刻状态 ----------

def now_status(pos_fn, lat, lon_east, h0, t_now: datetime):
    """    
    计算目标天体在当前时刻的位置，以及未来的升落时间，默认使用北京时间。
    输入: 
        pos_fn:用于计算天体在天球上的坐标的函数,
        lat, lon_east:观测地点经纬度,
        h0:几何高度阈值，大气折射，视半径，视差的修正,
        t_now:北京时间的当前时间
    输出：{
        "status":天体状态,
        "altitude":天体当前高度,
        "next_transit_time":下一次中天时间,
        "next_transit_high":下一次中天高度,
        "next_set_time":下一次落下时间,
        "next_rise_time":下一次升起时间
        }"""
    t_ut = t_now - timedelta(hours=8)
    base0 = t_ut.replace(hour=0, minute=0, second=0, microsecond=0)

    ra, dec = pos_fn(t_ut)
    theta = (gmst0(base0) + 360.985647 * (t_ut - base0).total_seconds()/86400) % 360
    H = wrap180(theta - (-lon_east) - ra*15)
    lat_rad = math.radians(lat)
    dec_rad = math.radians(dec)
    alt = math.degrees(math.asin(math.sin(lat_rad)*math.sin(dec_rad) + math.cos(lat_rad)*math.cos(dec_rad)*math.cos(math.radians(H))))

    if alt > h0:
        status = "above"
    else:
        status = "below"

    bases = [base0 + timedelta(days=k) for k in range(2)]
    events = _collect_events(pos_fn, lat, lon_east, h0, bases)

    nxt = {"rise_time": None, "transit_time": None, "set_time": None, "transit_high": None}
    for kind, t_cn in events:
        if kind == "transit_time":
            if t_cn[0] > t_now:
                if nxt[kind] is None or t_cn[0] < nxt[kind]:
                    nxt[kind] = t_cn[0]
                    nxt["transit_high"] = t_cn[1]
        else:
            if t_cn > t_now:
                if nxt[kind] is None or t_cn < nxt[kind]:
                    nxt[kind] = t_cn
  
    def fmt(dt):
        return dt.strftime("%m-%d %H:%M") if dt else None

    def fmh(h):
        return f"{h:.1f}°" if h else None

    return {
        "status": status,
        "altitude": f"{alt:.1f}°",
        "next_transit_time":fmt(nxt["transit_time"]),
        "next_transit_high":fmh(nxt["transit_high"]),
        "next_set_time":fmt(nxt["set_time"]),
        "next_rise_time":fmt(nxt["rise_time"])
        }

# ---------- 支持统计 ----------
BODIES = {"SUN": (sun_pos, SUN_H0)}

# ---------- 命令解析 ----------
def _parse_riseset_args(text: str):
    """
    '2026-11-04 SUN' → (day, pos_fn, h0)，解析失败抛 ValueError(中文提示)
    """
    parts = text.split()
    day, body = None, "SUN"

    for p in parts:
        if "-" in p:                                   # 带横线的一段当日期
            day = datetime.strptime(p, "%Y-%m-%d")     # 格式不对自动抛 ValueError
        else:
            body = p.upper()

    if body not in BODIES:
        raise ValueError(f"暂时只支持 SUN，收到的是 {body}")
    if day is None:                                    # 只给天体没给日期 → 今天
        day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return day, body, *BODIES[body]

if __name__ == "__main__":
    # sun_pos 若在本文件上方定义则直接用；在别的模块就改成 import
    from datetime import date
    today = datetime.combine(date.today(), datetime.min.time())
    print(day_riseset(sun_pos, 31.94, 118.79, SUN_H0, today))
    print(now_status(sun_pos, 31.94, 118.79, SUN_H0, datetime.now()))





