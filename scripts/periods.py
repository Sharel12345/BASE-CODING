"""Deterministic reporting-window helper (stdlib, offline).

Rule (mirrors the existing scheduled task; weekly = delivery cadence, NOT a 7-day analysis window):
  current    = the LAST TWO COMPLETE Sunday-Saturday weeks (14 days) in the account timezone
  comparison = the 14 days immediately preceding `current`
A Saturday is complete only after it ends, so the last complete Saturday is the latest Saturday
strictly before the as-of date (as-of Saturday -> previous Saturday; as-of Sunday -> yesterday).
Each window is pulled with its own explicit time_range (never a date_preset / combined range).
"""
import datetime as dt
from zoneinfo import ZoneInfo

DEFAULT_TZ = "Asia/Jerusalem"


def as_of_date(now=None, tz=DEFAULT_TZ):
    """Calendar date in the account timezone (accepts date, aware/naive datetime, ISO string, or None=now)."""
    if now is None:
        return dt.datetime.now(ZoneInfo(tz)).date()
    if isinstance(now, str):
        return dt.date.fromisoformat(now[:10])
    if isinstance(now, dt.datetime):
        return (now.astimezone(ZoneInfo(tz)) if now.tzinfo else now).date()
    return now


def reporting_windows(now=None, tz=DEFAULT_TZ):
    d = as_of_date(now, tz)
    last_sat = d - dt.timedelta(days=(d.weekday() - 5) % 7 or 7)  # latest Saturday strictly before d
    cur_start = last_sat - dt.timedelta(days=13)
    cmp_end = cur_start - dt.timedelta(days=1)
    cmp_start = cmp_end - dt.timedelta(days=13)
    iso = lambda x: x.isoformat()
    return {"as_of": iso(d), "timezone": tz,
            "current": {"start": iso(cur_start), "end": iso(last_sat), "days": 14},
            "comparison": {"start": iso(cmp_start), "end": iso(cmp_end), "days": 14},
            "pulls": [{"label": "current", "time_range": {"since": iso(cur_start), "until": iso(last_sat)}},
                      {"label": "comparison", "time_range": {"since": iso(cmp_start), "until": iso(cmp_end)}}]}


if __name__ == "__main__":
    import json, sys
    print(json.dumps(reporting_windows(sys.argv[1] if len(sys.argv) > 1 else None), indent=2))
