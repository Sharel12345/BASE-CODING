"""Deterministic offline analyzer for the verified TaskFlow task schema. Read-only; inputs not mutated.

Task fields used: id, title, client (name str), project (name str), assignee (dict|None),
due_date ('YYYY-MM-DD'|None), status (todo|doing|approval|done), approval_type
(client|manager|None), revision (bool), created_at_local, url, external_task_key.
Client/project matching is by NAME ONLY and is unverified: no stable IDs exist.
"""
import copy
import datetime as dt
import re
import zoneinfo

TZ = zoneinfo.ZoneInfo("Asia/Jerusalem")
DONE = {"done", "closed", "cancelled"}
UPCOMING_DAYS = 3


def israel_today(now=None):
    return (now or dt.datetime.now(TZ)).astimezone(TZ).date()


def _tokens(s):
    return {t for t in re.findall(r"\w+", (s or "").lower()) if len(t) > 1}


def similar(a, b):
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.6


def _norm(s):
    return " ".join((s or "").split()).casefold()


def _day(v):
    return dt.date.fromisoformat(v[:10]) if v else None


def analyze(tasks, proposals, today):
    tasks = copy.deepcopy(tasks)
    today = dt.date.fromisoformat(today) if isinstance(today, str) else today
    open_ = [t for t in tasks if t.get("status") not in DONE]
    ref = lambda t, **x: {"task_id": t["id"], "client": t.get("client"), "project": t.get("project"),
                          "url": t.get("url"), "title": t.get("title"), **x}
    out = {"as_of": today.isoformat(), "timezone": "Asia/Jerusalem",
           "totals": {"all": len(tasks), "open": len(open_), "done": len(tasks) - len(open_)},
           "mapping": {"basis": "names_only", "verified": False},
           "overdue": [], "due_today": [], "upcoming": [], "no_owner": [],
           "awaiting_client_approval": [], "awaiting_manager_approval": [], "approval_untyped": [],
           "revision": [], "no_due_date": [], "blocked": [], "ambiguous_names": [],
           "time_in_approval": "unknown (no status-change timestamp in data)",
           "proposals": [], "duplicates": []}
    for t in open_:
        due = _day(t.get("due_date"))
        if due is None:
            out["no_due_date"].append(ref(t, basis="fact"))
        elif due < today:
            out["overdue"].append(ref(t, basis="fact", due_date=t["due_date"], days_late=(today - due).days))
        elif due == today:
            out["due_today"].append(ref(t, basis="fact", due_date=t["due_date"]))
        elif (due - today).days <= UPCOMING_DAYS:
            out["upcoming"].append(ref(t, basis="fact", due_date=t["due_date"]))
        if not t.get("assignee"):
            out["no_owner"].append(ref(t, basis="fact"))
        if t.get("status") == "approval":
            kind = t.get("approval_type")
            key = {"client": "awaiting_client_approval", "manager": "awaiting_manager_approval"}.get(kind, "approval_untyped")
            out[key].append(ref(t, basis="fact"))
        if t.get("revision"):
            out["revision"].append(ref(t, basis="fact"))
        # no explicit blocker field exists in the data: nothing is ever inferred as blocked
    for field in ("client", "project"):
        variants = {}
        for t in tasks:
            if t.get(field):
                variants.setdefault(_norm(t[field]), set()).add(t[field])
        out["ambiguous_names"] += [{"field": field, "variants": sorted(v)} for v in variants.values() if len(v) > 1]
    for p in proposals:
        same = [t for t in tasks if _norm(t.get("client")) == _norm(p.get("client"))
                and _norm(t.get("project")) == _norm(p.get("project"))]
        hit = [t for t in same if (p.get("source_reference") and p["source_reference"] == t.get("external_task_key"))
               or similar(p["title"], t["title"])]
        if hit:
            out["duplicates"].append({"proposal_id": p["id"], "existing_task_id": hit[0]["id"]})
            continue
        creative = p.get("kind") == "creative_idea"
        out["proposals"].append({
            "title": p["title"], "description": p.get("description"),
            "client_id": None, "project_id": None,  # no stable IDs exist; never invented
            "client_name": p.get("client"), "project_name": p.get("project"),
            "mapping_status": "unverified_name_based",
            "suggested_assignee_id": p.get("suggested_assignee_id"),
            "suggested_due_date": p.get("suggested_due_date"),
            "priority": p.get("priority"), "source_reference": p.get("source_reference"),
            "approval_status": "proposed_unapproved" if creative and not p.get("approved") else "pending_review"})
    return out
