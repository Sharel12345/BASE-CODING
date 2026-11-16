"""Meta extraction coverage check (offline, stdlib). Distinguishes extraction completeness from funnel gaps.

Rows (per period): ads=[{ad,adset,campaign,spend,impressions,link_clicks,leads}] must cover EVERY positive-spend
ad (including zero-lead and low-spend ads). Totals dicts are independently pulled adset/campaign/account totals:
adsets={adset_id: {spend,impressions,link_clicks,leads}}, campaigns={...}, account={...}.
Only additive metrics are reconciled. reach, frequency and ratios (CPL, CTR, ...) are NEVER summed.
"""
ADDITIVE = ("spend", "impressions", "link_clicks", "leads")
SPEND_TOL = 0.05  # rounding tolerance in currency units; counts must match exactly


def _sum(rows):
    return {m: sum(r.get(m) or 0 for r in rows) for m in ADDITIVE}


def _diff(got, want):
    return {m: round(got[m] - (want.get(m) or 0), 2) for m in ADDITIVE}


def _bad(d):
    return any(abs(v) > (SPEND_TOL if m == "spend" else 0) for m, v in d.items())


def reconcile(ads, adsets, campaigns, account, pagination=None):
    """pagination: None/{} when the tool returned no cursor metadata, else {'next_cursor': ..., 'pages': n}."""
    issues, ids = [], [a.get("ad") for a in ads]
    if any(not i for i in ids):
        issues.append("ad row without id")
    dups = sorted({i for i in ids if i and ids.count(i) > 1})
    if dups:
        issues.append(f"duplicate ad ids: {len(dups)}")
    if any((a.get("spend") or 0) <= 0 for a in ads):
        issues.append("non-positive-spend ad row present (extraction must be positive-spend only)")
    levels = {"adset": ("adset", adsets), "campaign": ("campaign", campaigns)}
    out = {"ad_count": len(ads), "zero_lead_ads": sum(1 for a in ads if not a.get("leads")), "levels": {}}
    out["ads_total"] = _sum(ads)
    out["account_diff"] = _diff(out["ads_total"], account)
    if _bad(out["account_diff"]):
        issues.append("ads != account")
    for name, (key, totals) in levels.items():
        res = {}
        for tid, want in totals.items():
            d = _diff(_sum([a for a in ads if a.get(key) == tid]), want)
            res[tid] = d
            if _bad(d):
                issues.append(f"ads != {name} {tid}")
        unknown = sorted({a.get(key) for a in ads} - set(totals))
        if unknown:
            issues.append(f"ads reference {name} ids without totals: {len(unknown)}")
        out["levels"][name] = res
    sums = _sum(list(adsets.values()))
    if _bad(_diff(sums, account)):
        issues.append("adset totals != account")  # catches missing adsets (zero-spend-only/hidden entities)
    sums = _sum(list(campaigns.values()))
    if _bad(_diff(sums, account)):
        issues.append("campaign totals != account")
    cursor_meta = bool(pagination) and "next_cursor" in pagination
    out["pagination"] = {"cursor_metadata_present": cursor_meta,
                         "next_cursor": (pagination or {}).get("next_cursor") if cursor_meta else None}
    if cursor_meta and pagination.get("next_cursor"):
        issues.append("next_cursor still set: read incomplete")
    out["completeness_basis"] = ("pagination_metadata_and_reconciliation" if cursor_meta and not issues else
                                 "reconciliation_only_no_cursor_metadata" if not cursor_meta and not issues else "failed")
    out["issues"], out["complete"] = issues, not issues
    return out
