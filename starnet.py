import time
from urllib.request import urlopen
from urllib.error import URLError
from urllib.parse import urlencode
import json
from datetime import datetime, timedelta

_cache = {}    # 晴天钟调用缓存
_TTL = 1800    # 缓存有效期 30 分钟，单位秒

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


def fetch_astro(lat, lon):
    # ① 缓存检查：模块级 _cache = {}，key=(round(lat,2), round(lon,2))，
    #    value=(time.monotonic(), data)；半小时内直接返回旧数据
    # ② 拼 URL："https://www.7timer.info/bin/api.pl?" + urlencode({...})
    # ③ 拉取：try 里 urlopen(url, timeout=10).read()
    # ④ 解析：json.loads → data
    # ⑤ 基本校验：data 里有 "init" 和 "dataseries" 才算数，否则 None
    # ⑥ 写缓存，返回 data（原样 dict，不做任何加工）
    pass