"""Versioned handoff contracts: stdlib JSON-Schema-subset validator, provenance checks, review gates.
Offline, no network. Supported keywords: type, const, enum, required, properties,
additionalProperties(false), items, minItems, maxItems."""
import json
import pathlib

SCHEMAS = pathlib.Path(__file__).resolve().parent.parent / "schemas"
NAMES = {"performance_findings": "findings", "creative_proposals": "proposals",
         "evidence_review": "evidence_review", "manager_task_drafts": "task_drafts"}
_TYPES = {"string": str, "integer": int, "boolean": bool, "object": dict, "array": list, "null": type(None)}


def load_schema(artifact):
    return json.loads((SCHEMAS / f"{NAMES[artifact]}.v1.schema.json").read_text())


def _check(v, s, path, errs):
    if "const" in s and v != s["const"]:
        errs.append(f"{path}: expected {s['const']!r}"); return
    if "enum" in s and v not in s["enum"]:
        errs.append(f"{path}: {v!r} not in {s['enum']}"); return
    t = s.get("type")
    if t:
        ts = t if isinstance(t, list) else [t]
        okt = any(isinstance(v, _TYPES[x]) and not (x == "integer" and isinstance(v, bool)) for x in ts)
        if not okt:
            errs.append(f"{path}: expected {ts}"); return
    if isinstance(v, dict):
        for k in s.get("required", []):
            if k not in v: errs.append(f"{path}.{k}: missing")
        props = s.get("properties", {})
        if s.get("additionalProperties") is False:
            for k in v:
                if k not in props: errs.append(f"{path}.{k}: unexpected field")
        for k, sub in props.items():
            if k in v: _check(v[k], sub, f"{path}.{k}", errs)
    if isinstance(v, list):
        if "minItems" in s and len(v) < s["minItems"]: errs.append(f"{path}: fewer than {s['minItems']} items")
        if "maxItems" in s and len(v) > s["maxItems"]: errs.append(f"{path}: more than {s['maxItems']} items")
        for i, x in enumerate(v):
            if "items" in s: _check(x, s["items"], f"{path}[{i}]", errs)


def validate(doc):
    """Return list of errors ([] = valid). Rejects unknown artifact/version."""
    if not isinstance(doc, dict) or doc.get("artifact") not in NAMES:
        return ["unknown artifact"]
    if doc.get("schema_version") != "1.0":
        return [f"unsupported schema_version: {doc.get('schema_version')!r}"]
    errs = []
    _check(doc, load_schema(doc["artifact"]), "$", errs)
    return errs


def check_provenance(findings, proposals, review=None):
    """Cross-artifact integrity: run/period continuity and evidence references preserved."""
    errs = []
    if proposals["source_findings_run_id"] != findings["run_id"]:
        errs.append("proposals.source_findings_run_id != findings.run_id")
    if proposals["period"] != findings["period"]:
        errs.append("proposals period differs from findings period")
    fids = {f["finding_id"] for f in findings["findings"]}
    refs = {e["source_ref"] for f in findings["findings"] for e in f["evidence"]}
    for p in proposals["proposals"]:
        for fid in p["source_finding_ids"]:
            if fid not in fids: errs.append(f"{p['proposal_id']}: unknown finding {fid}")
        for r in p["source_refs"]:
            if r not in refs: errs.append(f"{p['proposal_id']}: source_ref {r} not in findings evidence")
    if review is not None:
        if review["proposals_run_id"] != proposals["run_id"]:
            errs.append("review.proposals_run_id != proposals.run_id")
        if review["period"] != proposals["period"]:
            errs.append("review period differs from proposals period")
        known = {p["proposal_id"] for p in proposals["proposals"]}
        for rv in review["reviews"]:
            if rv["proposal_id"] not in known: errs.append(f"review for unknown proposal {rv['proposal_id']}")
    return errs


def review_gate(proposals, review):
    """Return (passed_ids, blocked[{proposal_id, reason}]). Failed upstream or failed review blocks."""
    passed, blocked = [], []
    upstream_ok = proposals["status"] == "complete" and (review or {}).get("status") == "complete"
    verdicts = {r["proposal_id"]: r for r in (review or {}).get("reviews", [])}
    for p in proposals["proposals"]:
        rv = verdicts.get(p["proposal_id"])
        if not upstream_ok:
            blocked.append({"proposal_id": p["proposal_id"], "reason": "upstream step not complete"})
        elif rv is None:
            blocked.append({"proposal_id": p["proposal_id"], "reason": "no evidence review"})
        elif rv["verdict"] != "supported":
            blocked.append({"proposal_id": p["proposal_id"], "reason": f"review verdict: {rv['verdict']}"})
        else:
            passed.append(p["proposal_id"])
    return passed, blocked
