"""Deterministic regression checks for the reporting-window rule (synthetic dates only)."""
import datetime as dt, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from zoneinfo import ZoneInfo
from periods import reporting_windows as rw

ok = True
def check(n, c):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + n)
def span(w): return (w["current"]["start"], w["current"]["end"], w["comparison"]["start"], w["comparison"]["end"])

check("as of Mon 2026-11-16", span(rw("2026-11-16")) == ("2026-11-01", "2026-11-14", "2026-10-18", "2026-10-31"))
check("as of Sun 2026-11-22", span(rw("2026-11-22")) == ("2026-11-08", "2026-11-21", "2026-10-25", "2026-11-07"))
check("as of Sat 2026-11-21 (Saturday not yet complete)", span(rw("2026-11-21")) == ("2026-11-01", "2026-11-14", "2026-10-18", "2026-10-31"))
check("as of Sun 2026-11-15", span(rw("2026-11-15")) == ("2026-11-01", "2026-11-14", "2026-10-18", "2026-10-31"))
for iso in ("2026-11-16", "2026-11-22", "2026-12-30", "2027-01-01", "2026-03-27"):  # incl. DST and year boundaries
    w = rw(iso); c, p = w["current"], w["comparison"]
    cs, ce, ps, pe = (dt.date.fromisoformat(x) for x in (c["start"], c["end"], p["start"], p["end"]))
    check(f"{iso}: Sun-Sat, 14 days each, adjacent, ends before as-of",
          cs.weekday() == 6 and ce.weekday() == 5 and ps.weekday() == 6 and pe.weekday() == 5
          and (ce - cs).days == 13 and (pe - ps).days == 13 and (cs - pe).days == 1 and ce < dt.date.fromisoformat(iso))
w = rw("2026-11-16")
check("two separate explicit time_range pulls", [p["label"] for p in w["pulls"]] == ["current", "comparison"]
      and w["pulls"][0]["time_range"] == {"since": "2026-11-01", "until": "2026-11-14"}
      and w["pulls"][1]["time_range"] == {"since": "2026-10-18", "until": "2026-10-31"})
check("timezone default Asia/Jerusalem", w["timezone"] == "Asia/Jerusalem")
late_utc = dt.datetime(2026, 11, 21, 22, 30, tzinfo=dt.timezone.utc)  # already Sun 2026-11-22 00:30 in Jerusalem
check("aware datetime converted to account timezone", rw(late_utc)["as_of"] == "2026-11-22" and span(rw(late_utc)) == span(rw("2026-11-22")))
check("naive/date inputs accepted", span(rw(dt.date(2026, 11, 16))) == span(rw("2026-11-16")))
wf = (ROOT / "workflows/weekly-performance.md").read_text(); pa = (ROOT / ".claude/agents/performance-analyst.md").read_text()
check("workflow states 14-vs-14 rule and delivery cadence", "LAST TWO COMPLETE" in wf and "delivery cadence" in wf and "scripts/periods.py" in wf)
check("workflow labels 7-vs-7 pilot as historical integration test", "historical integration test" in wf)
check("performance-analyst default window is 14 vs 14", "LAST TWO COMPLETE" in pa and "scripts/periods.py" in pa)
sys.exit(0 if ok else 1)
