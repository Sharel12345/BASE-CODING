"""Deterministic, offline reference analyzer. Read-only: no network, no writes, inputs not mutated."""
import copy
import datetime as dt
import re

DONE = {"done", "closed", "cancelled"}
UPCOMING_DAYS = 3


def _tokens(s):
    return {t for t in re.findall(r"\w+", (s or "").lower()) if len(t) > 1}


def similar(a, b):
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.6


def analyze(snapshot, proposals, today):
    snap = copy.deepcopy(snapshot)
    today = dt.date.fromisoformat(today)
    open_tasks = [t for t in snap["tasks"] if t.get("status") not in DONE]
    out = {"overdue": [], "upcoming": [], "awaiting_approval": [], "blocked": [],
           "no_owner": [], "proposals": [], "duplicates": [], "decisions_needed": []}
    for t in open_tasks:
        ref = {"task_id": t["id"], "project_id": t["project_id"], "client_id": t["client_id"]}
        due = dt.date.fromisoformat(t["due_date"]) if t.get("due_date") else None
        if due and due < today:
            out["overdue"].append({**ref, "basis": "fact", "days_late": (today - due).days})
        elif due and (due - today).days <= UPCOMING_DAYS:
            out["upcoming"].append({**ref, "basis": "fact"})
        if t.get("awaiting") == "client_approval":
            out["awaiting_approval"].append({**ref, "basis": "fact"})
        if t.get("blocker"):  # explicit only; inactivity never counts
            out["blocked"].append({**ref, "basis": "fact", "blocker": t["blocker"]})
        if not t.get("assignee_id"):
            out["no_owner"].append({**ref, "basis": "fact"})
            out["decisions_needed"].append({**ref, "decision": "assign_owner"})
    for p in proposals:
        existing = [t for t in snap["tasks"] if t["project_id"] == p["project_id"] and (
            (p.get("source_reference") and p["source_reference"] == t.get("source_reference"))
            or similar(p["title"], t["title"]))]
        if existing:
            out["duplicates"].append({"proposal_id": p["id"], "existing_task_id": existing[0]["id"]})
            continue
        creative = p.get("kind") == "creative_idea"
        out["proposals"].append({
            "title": p["title"], "description": p.get("description"),
            "client_id": p["client_id"], "project_id": p["project_id"],
            "suggested_assignee_id": p.get("suggested_assignee_id"),
            "suggested_due_date": p.get("suggested_due_date"),
            "priority": p.get("priority"), "source_reference": p.get("source_reference"),
            "approval_status": "proposed_unapproved" if creative and not p.get("approved")
            else "pending_review",
        })
    return out
