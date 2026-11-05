import math
from functools import partial
from datetime import datetime, timedelta

SUN_H0 = -0.833
MOON_H0 = 0.125
STAR_H0 = -0.567

LON_TERMS = [
    # (振幅,  M',  D,  F,  M, 乘E)
    ( 6.288774,  1, 0,  0,  0, 1),
    ( 1.274027, -1, 2,  0,  0, 1),
    ( 0.658314,  0, 2,  0,  0, 1),
    ( 0.213618,  2, 0,  0,  0, 1),
    (-0.185116,  0, 0,  0,  1, 1),
    (-0.114332,  0, 0,  2,  0, 0),
    ( 0.058793, -2, 2,  0,  0, 0),
    ( 0.057066, -1, 2,  0, -1, 1),
    ( 0.053322,  1, 2,  0,  0, 1),
    ( 0.045758,  0, 2,  0, -1, 0),
    (-0.040923, -1, 0,  0,  1, 1),
    (-0.034720,  0, 1,  0,  0, 0),
    (-0.030383,  1, 0,  0,  1, 1),
    ( 0.015327,  0, 2, -2,  0, 0),
]

LAT_TERMS = [
    # (振幅,  M',  D,  F)
    (5.128122,  0, 0,  1),
    (0.280602,  1, 0,  1),
    (0.277693,  1, 0, -1),
    (0.173238,  0, 2, -1),
    (0.055413, -1, 2,  1),
    (0.046272, -1, 2, -1),
    (0.032573,  0, 2,  1),
    (0.017198,  1, 2, -1),
]

DEL_TERMS = [
    # (振幅km,  M',  D,  F,  M)
    (-20905.355,  1,  0, 0, 0),   # cos(M')
    ( -3699.111, -1,  2, 0, 0),   # cos(2D - M')
    ( -2955.968,  0,  2, 0, 0),   # cos(2D)
    (  -569.925,  2,  0, 0, 0),   # cos(2M')
    (    48.888,  0,  0, 0, 1),   # cos(M)
    (    -3.149,  0,  0, 2, 0),   # cos(2F)
    (   246.158,  2, -2, 0, 0),   # cos(2M' - 2D)
    (  -152.138,  1, -2, 0, 1),   # cos(M + M' - 2D)
]

PLANET_ELEMENTS = {
    #          a(AU)        e          i(°)       L(°)        ϖ(°)       Ω(°)
    "MERCURY": ((0.38709927, 0.00000037), (0.20563593, 0.00001906), (7.00497902, -0.00594749), (252.25032350, 149472.67411175), (77.45779628, 0.16047689), (48.33076593, -0.12534081)),
    "VENUS":   ((0.72333566, 0.00000390), (0.00677672, -0.00004107), (3.39467605, -0.00078890), (181.97909950, 58517.81538729), (131.56460914, 0.00268329), (76.67984255, -0.27769418)),
    "EARTH":   ((1.00000261, 0.00000562), (0.01671123, -0.00004392), (-0.00001531, -0.01294668), (100.46457166, 35999.37244981), (102.93768193, 0.32327364), (0.0, 0.0)),
    "MARS":    ((1.52371034, 0.00001847), (0.09339410, 0.00007882), (1.84969142, -0.00813131), (-4.55343205, 19140.30268499), (-23.94362959, 0.44441088), (49.55953891, -0.29257343)),
    "JUPITER": ((5.20288700, -0.00011607), (0.04838624, -0.00013253), (1.30439695, -0.00183714), (34.39644051, 3034.74612775), (14.72847983, 0.21252668), (100.47390909, 0.20469106)),
    "SATURN":  ((9.53667594, -0.00125060), (0.05386179, -0.00050991), (2.48599187, 0.00193609), (49.95424423, 1222.49362201), (92.59887831, -0.41897216), (113.66242448, -0.28867794)),
    "URANUS":  ((19.18916464, -0.00196176), (0.04725744, -0.00004397), (0.77263783, -0.00242939), (313.23810451, 428.48202785), (170.95427630, 0.40805281), (74.01692503, 0.04240589)),
    "NEPTUNE": ((30.06992276, 0.00026291), (0.00859048, 0.00005105), (1.77004347, 0.00035372), (-55.12002969, 218.45945325), (44.96476227, -0.32241464), (131.78422574, -0.00508664)),
}


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

def moon_pos(t: datetime):
    """
    计算目标时间月亮在天球上的坐标。
    输入: 一个 datetime UTC
    返回: (赤经(小时), 赤纬(度))
    """
    T =  d_j2000(t) / 36525

    L_m = 218.3164477 + 481267.88123421*T - 0.0015786*T**2 + T**3/538841 - T**4/65194000    # 月亮平黄经
    M  = 357.5291092 + 35999.0502909*T - 0.0001536*T**2 + T**3/24490000                     # 太阳平近点角
    M_m = 134.9633964 + 477198.8675055*T + 0.0087414*T**2 + T**3/69699 - T**4/14712000      # 月亮平近点角

    D  = 297.8501921 + 445267.1114034*T - 0.0018819*T**2 + T**3/545868 - T**4/113065000
    F  = 93.2720950 + 483202.0175233*T - 0.0036539*T**2 - T**3/3526000 + T**4/863310000
    E = 1 - 0.002516*T - 0.0000074*T**2                                                     # 地球轨道偏心率因子（带 M 的项要乘 E）

    def sin(x):
        return math.sin(math.radians(x))
    
    def cos(x):
        return math.cos(math.radians(x))

    λ = L_m + sum(C0*sin(C1*M_m+C2*D+C3*F+C4*M) * (E if C5 else 1.0) for C0, C1, C2, C3, C4, C5 in LON_TERMS)         # 月亮黄经
    β = sum(C0*sin(C1*M_m+C2*D+C3*F) for C0, C1, C2, C3 in LAT_TERMS)                                                 # 月亮黄纬
    Δ = 385000.56 + sum(C0*cos(C1*M_m+C2*D+C3*F+C4*M) for C0, C1, C2, C3, C4 in DEL_TERMS)                            # 月地距离(km)

    ε = 23.4392911 - 0.0130042*T
    λ_rad = math.radians(λ)
    β_rad = math.radians(β)
    ε_rad = math.radians(ε)

    RA = math.atan2(math.sin(λ_rad)*math.cos(ε_rad) - math.tan(β_rad)*math.sin(ε_rad), math.cos(λ_rad))
    Dec = math.asin(math.sin(β_rad)*math.cos(ε_rad) + math.cos(β_rad)*math.sin(ε_rad)*math.sin(λ_rad))

    dec_deg = math.degrees(Dec)
    ra_hours = math.degrees(RA) / 15 % 24

    return (ra_hours, dec_deg)

def planet_pos(t: datetime, name):
    """
    计算目标时间各行星在天球上的坐标。
    输入: 一个 datetime UTC，行星名称（如MARS）name
    返回: (赤经(小时), 赤纬(度))
    """

    T =  d_j2000(t) / 36525

    def iterate(M_r, e_r):
        """
        解开普勒方程 E - e*sin(E) = M  （M、E 均为弧度）
        返回偏近点角 E
        """
        E = M_r
        for _ in range(5):
            f = E - e_r*math.sin(E) - M_r
            fp = 1 - e_r*math.cos(E)
            E = E - f/fp
        return E

    def root_to_xyz(n):
        (a, d_a), (e, d_e), (i, d_i), (l, d_l), (o, d_o), (Ω, d_Ω) = PLANET_ELEMENTS[n]

        # 轨道六根数 
        a += d_a*T
        e += d_e*T
        i += d_i*T
        l += d_l*T
        o += d_o*T
        Ω += d_Ω*T

        ω = o - Ω               # 近日点幅角
        M = wrap180(l - o)      # 平近点角

        E = iterate(math.radians(M), e)

        x_orb = a*(math.cos(E) - e)
        y_orb = a*math.sqrt((1-e**2))*math.sin(E)

        cosΩ = math.cos(math.radians(Ω))
        sinΩ = math.sin(math.radians(Ω))
        cosω = math.cos(math.radians(ω))
        sinω = math.sin(math.radians(ω))
        cosi = math.cos(math.radians(i))
        sini = math.sin(math.radians(i))

        x = (cosΩ*cosω - sinΩ*sinω*cosi)*x_orb + (-cosΩ*sinω - sinΩ*cosω*cosi)*y_orb
        y = (sinΩ*cosω + cosΩ*sinω*cosi)*x_orb + (-sinΩ*sinω + cosΩ*cosω*cosi)*y_orb
        z = (sinω*sini)*x_orb + (cosω*sini)*y_orb

        return x, y, z


    planet_x, planet_y, planet_z = root_to_xyz(name)
    earth_x, earth_y, earth_z = root_to_xyz("EARTH")

    real_x = planet_x - earth_x
    real_y = planet_y - earth_y
    real_z = planet_z - earth_z

    λ_rad = math.atan2(real_y, real_x)
    β_rad = math.atan2(real_z, math.sqrt(real_x**2 + real_y**2))

    ε = 23.4392911
    ε_rad = math.radians(ε)

    RA = math.atan2(math.sin(λ_rad)*math.cos(ε_rad) - math.tan(β_rad)*math.sin(ε_rad), math.cos(λ_rad))
    Dec = math.asin(math.sin(β_rad)*math.cos(ε_rad) + math.cos(β_rad)*math.sin(ε_rad)*math.sin(λ_rad))

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
        status = "地平上"
    else:
        status = "已落下"

    bases = [base0 + timedelta(days=k) for k in range(2)]
    events = _collect_events(pos_fn, lat, lon_east, h0, bases)

    nxt = {"rise_time": None, "transit_time": None, "set_time": None, "transit_high": None}
    for kind, t_cn in events:
        if kind == "transit_time":
            if t_cn[0] > t_now and (nxt[kind] is None or t_cn[0] < nxt[kind]):
                nxt[kind] = t_cn[0]
                nxt["transit_high"] = t_cn[1]
        else:
            if t_cn > t_now and (nxt[kind] is None or t_cn < nxt[kind]):
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
BODIES = {"SUN": (sun_pos, SUN_H0),
          "MOON": (moon_pos, MOON_H0),
          "MERCURY":  (partial(planet_pos, name="MERCURY"), STAR_H0),
          "VENUS":  (partial(planet_pos, name="VENUS"), STAR_H0),
          "MARS":  (partial(planet_pos, name="MARS"), STAR_H0),
          "JUPITER":  (partial(planet_pos, name="JUPITER"), STAR_H0),
          "SATURN":  (partial(planet_pos, name="SATURN"), STAR_H0),
          "URANUS":  (partial(planet_pos, name="URANUS"), STAR_H0),
          "NEPTUNE":  (partial(planet_pos, name="NEPTUNE"), STAR_H0)}

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
        raise ValueError(f"暂时只支持{'、'.join(BODIES)}，收到的是 {body}")
    if day is None:                                    # 只给天体没给日期 → 今天
        day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return day, body, *BODIES[body]

if __name__ == "__main__":
    # sun_pos 若在本文件上方定义则直接用；在别的模块就改成 import
    from datetime import date
    today = datetime.combine(date.today(), datetime.min.time())
    test = datetime(1992,4,12,0,0,0)

    print(moon_pos(test))
    print(day_riseset(moon_pos, 31.94, 118.79, MOON_H0, today))
    print(now_status(moon_pos, 31.94, 118.79, MOON_H0, datetime.now()))





