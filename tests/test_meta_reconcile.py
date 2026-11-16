"""Synthetic tests for Meta extraction coverage reconciliation (no real data)."""
import copy, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from meta_reconcile import reconcile

ok = True
def check(n, c):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + n)

def row(a, ad_set, camp, sp, im, lc, ld):
    return {"ad": a, "adset": ad_set, "campaign": camp, "spend": sp, "impressions": im, "link_clicks": lc, "leads": ld}
ADS = [row("A1", "S1", "C1", 100.0, 1000, 10, 2), row("A2", "S1", "C1", 0.01, 3, 0, 0),
       row("A3", "S2", "C1", 50.5, 500, 5, 0), row("A4", "S3", "C2", 20.0, 200, 2, 1)]
ADSETS = {"S1": dict(spend=100.01, impressions=1003, link_clicks=10, leads=2), "S2": dict(spend=50.5, impressions=500, link_clicks=5, leads=0),
          "S3": dict(spend=20.0, impressions=200, link_clicks=2, leads=1)}
CAMPS = {"C1": dict(spend=150.51, impressions=1503, link_clicks=15, leads=2), "C2": dict(spend=20.0, impressions=200, link_clicks=2, leads=1)}
ACC = dict(spend=170.51, impressions=1703, link_clicks=17, leads=3)

r = reconcile(ADS, ADSETS, CAMPS, ACC)
check("full positive-spend population incl. zero-lead and 0.01 spend reconciles", r["complete"] and r["zero_lead_ads"] == 2 and r["ad_count"] == 4)
check("no cursor metadata -> reconciliation-only basis stated", r["completeness_basis"] == "reconciliation_only_no_cursor_metadata" and not r["pagination"]["cursor_metadata_present"])
r = reconcile(ADS, ADSETS, CAMPS, ACC, {"next_cursor": None, "pages": 1})
check("cursor metadata present and exhausted", r["complete"] and r["completeness_basis"] == "pagination_metadata_and_reconciliation")
r = reconcile(ADS, ADSETS, CAMPS, ACC, {"next_cursor": "abc"})
check("unexhausted cursor -> incomplete", not r["complete"] and r["completeness_basis"] == "failed")
# favorable-result sampling: dropping zero-lead / low-spend ads must fail even if leads still match
sampled = [a for a in ADS if a["leads"] > 0 or a["spend"] >= 20]
r = reconcile(sampled, ADSETS, CAMPS, ACC)
check("dropping zero-lead/low-spend ads fails although lead totals match", not r["complete"] and any("ads != account" in i for i in r["issues"]))
check("lead totals alone are not completeness", sum(a["leads"] for a in sampled) == ACC["leads"] and not r["complete"])
r = reconcile(ADS + [copy.deepcopy(ADS[0])], ADSETS, CAMPS, ACC)
check("duplicate ad ids detected", not r["complete"] and any("duplicate ad ids" in i for i in r["issues"]))
bad = copy.deepcopy(ADS); bad[3]["adset"] = "S1"
r = reconcile(bad, ADSETS, CAMPS, ACC)
check("misassigned adset detected at adset level", not r["complete"] and any("S1" in i or "S3" in i for i in r["issues"]))
r = reconcile(ADS, ADSETS, CAMPS, dict(ACC, leads=4))
check("lead mismatch vs account detected", not r["complete"])
r = reconcile(ADS, ADSETS, {"C1": CAMPS["C1"]}, ACC)
check("campaign totals missing a campaign detected", not r["complete"])
r = reconcile(ADS + [row("A5", "S9", "C9", 5.0, 50, 1, 0)], ADSETS, CAMPS, ACC)
check("ad referencing unknown adset/campaign detected", not r["complete"])
r = reconcile(ADS + [row("A6", "S1", "C1", 0, 0, 0, 0)], ADSETS, CAMPS, ACC)
check("zero-spend row rejected (positive-spend population only)", not r["complete"])
check("reach/frequency/ratios are never summed (not part of reconciled metrics)", set(reconcile(ADS, ADSETS, CAMPS, ACC)["ads_total"]) == {"spend", "impressions", "link_clicks", "leads"})
sys.exit(0 if ok else 1)
