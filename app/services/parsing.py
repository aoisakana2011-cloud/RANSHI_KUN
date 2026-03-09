# app/services/parsing.py
from datetime import datetime, date, time
from typing import Optional

def parse_datetime_str(dtstr: Optional[str]) -> Optional[datetime]:
    if not dtstr:
        return None
    s = dtstr.strip()
    fmts = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M")
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            t = datetime.strptime(s, fmt).time()
            return datetime.combine(datetime.now().date(), t)
        except Exception:
            continue
    return None

def parse_time_str(tstr: Optional[str]) -> Optional[time]:
    if not tstr:
        return None
    s = tstr.strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).time()
        except Exception:
            continue
    return None

def time_to_float(t: time) -> float:
    return t.hour + t.minute / 60.0 + t.second / 3600.0

def time_to_minutes(t: time) -> float:
    return t.hour * 60 + t.minute + t.second / 60.0

def minutes_to_time(minutes: float) -> time:
    m = int(round(minutes))
    h = (m // 60) % 24
    mm = m % 60
    return time(hour=h, minute=mm)

def time_weight_factor_from_timeobj(tobj: time) -> float:
    h = tobj.hour
    if 22 <= h or h < 6:
        return 1.45
    if 18 <= h < 22:
        return 1.20
    if 12 <= h < 18:
        return 1.05
    return 1.0

def sigmoid(x: float) -> float:
    import math
    return 1.0 / (1.0 + math.exp(-x))