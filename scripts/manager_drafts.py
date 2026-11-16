"""Manager step: reviewed proposals + COMPLETE TaskFlow read -> proposed task drafts only.
Pure function; no network, no writes. Owners/deadlines are never guessed (always null)."""
import hashlib

import re

from analyze import analyze, _norm
from handoff import review_gate



def _toks(s):
    return {t for t in re.findall(r"\w+", (s or "").lower()) if len(t) > 1}


def fuzzy_candidate(hook, title):
    """Candidate only (never a confirmed duplicate): >=2 shared tokens covering >=60% of the hook."""
    h, t = _toks(hook), _toks(title)
    return len(h & t) >= 2 and len(h & t) / len(h) >= 0.6


def draft_id(proposal, period):
    key = "|".join([proposal["proposal_id"], period["start"], *sorted(proposal["source_refs"])])
    return "d-" + hashlib.sha256(key.encode()).hexdigest()[:16]


def external_key(proposal, period):
    return f"wk:{period['start']}:{proposal['proposal_id']}"


def build(findings, proposals, review, tasks, tf_read, today):
    """tf_read: {complete, reported_count, fetched_count, issues} from the paginated read result."""
    out = {"schema_version": "1.0", "artifact": "manager_task_drafts", "run_id": proposals["run_id"],
           "period": proposals["period"], "overall_status": "complete", "issues": [],
           "taskflow_read": {"complete": bool(tf_read["complete"]), "reported_count": tf_read.get("reported_count"),
                             "fetched_count": tf_read["fetched_count"], "issues": list(tf_read.get("issues", []))},
           "drafts": [], "already_represented": [], "blocked_proposals": [],
           "workload": {"open": 0, "overdue": 0, "approvals_total": 0, "awaiting_client_approval": 0,
                        "awaiting_manager_approval": 0, "approval_untyped": 0, "no_owner": 0},
           "writes_performed": 0}
    for name, art in (("findings", findings), ("proposals", proposals), ("review", review)):
        if art["status"] == "failed":
            out["overall_status"] = "failed"; out["issues"].append(f"{name} failed")
        elif art["status"] == "partial" and out["overall_status"] != "failed":
            out["overall_status"] = "partial"; out["issues"].append(f"{name} partial")
    if not tf_read["complete"]:  # duplicate detection is unreliable on a partial read
        out["overall_status"] = "failed"; out["issues"].append("TaskFlow read incomplete: no drafts produced")
        out["blocked_proposals"] = [{"proposal_id": p["proposal_id"], "reason": "TaskFlow read incomplete"} for p in proposals["proposals"]]
        return out
    a = analyze(tasks, [], today)
    approvals_total = sum(1 for t in tasks if t.get("status") == "approval")  # independent count from the same snapshot
    out["workload"] = {"open": a["totals"]["open"], "overdue": len(a["overdue"]), "approvals_total": approvals_total,
                       "awaiting_client_approval": len(a["awaiting_client_approval"]),
                       "awaiting_manager_approval": len(a["awaiting_manager_approval"]),
                       "approval_untyped": len(a["approval_untyped"]), "no_owner": len(a["no_owner"])}
    w = out["workload"]
    if w["awaiting_client_approval"] + w["awaiting_manager_approval"] + w["approval_untyped"] != w["approvals_total"]:
        out["overall_status"] = "failed"
        out["issues"].append("workload invariant violated: approval subcounts do not sum to approvals_total")
        return out
    passed, blocked = review_gate(proposals, review)
    out["blocked_proposals"] = blocked
    for p in proposals["proposals"]:
        if p["proposal_id"] not in passed:
            continue
        ekey = external_key(p, proposals["period"])
        exact_keys = set(p["source_refs"]) | {ekey}
        cands, represented = [], None
        for t in tasks:
            if t.get("external_task_key") in exact_keys:
                c = {"task_id": t["id"], "url": t["url"], "match": "exact_source_reference", "task_status": t["status"],
                     "reason": "task external key equals this proposal's source reference / weekly key"}
                if t["status"] == "done":
                    c["reason"] += "; completed historical task does not prove this week's experiment was done"
                else:
                    represented = represented or c
                cands.append(c)
            elif (p["client_label"] is None or _norm(t.get("client")) == _norm(p["client_label"])) \
                    and fuzzy_candidate(p["hook"], t["title"]):
                cands.append({"task_id": t["id"], "url": t["url"], "match": "fuzzy_title", "task_status": t["status"],
                              "reason": "fuzzy title similarity only; not confirmed as the same work"})
        if represented:
            out["already_represented"].append({"proposal_id": p["proposal_id"], "task_id": represented["task_id"], "url": represented["url"]})
            continue
        out["drafts"].append({
            "draft_id": draft_id(p, proposals["period"]), "proposal_id": p["proposal_id"],
            "title": f"[הצעה] {p['hook']}"[:120], "description": f"{p['concept']}\n\n{p['primary_copy']}",
            "client_label": p["client_label"], "project_label": p["project_label"], "mapping_status": p["mapping_status"],
            "source_refs": list(p["source_refs"]), "hypothesis": "; ".join(p["hypotheses"]) or "none stated",
            "success_metric": p["test"]["metric"], "priority": "normal",
            "suggested_owner": None, "suggested_deadline": None, "proposed_external_task_key": ekey,
            "approval_status": "proposed_unapproved",
            "related_task_urls": sorted({c["url"] for c in cands}), "duplicate_candidates": cands})
    if blocked and out["overall_status"] == "complete":
        out["overall_status"] = "partial"; out["issues"].append("some proposals blocked by review gate")
    return out
