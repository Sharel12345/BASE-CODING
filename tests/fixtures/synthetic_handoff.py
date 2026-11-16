"""SYNTHETIC TEST DATA - NOT REAL. Builders for handoff-contract tests."""
import copy

PERIOD = {"start": "2026-01-04", "end": "2026-01-10", "timezone": "Asia/Jerusalem",
          "compare_start": "2025-12-28", "compare_end": "2026-01-03"}


def findings(status="complete"):
    return {"schema_version": "1.0", "artifact": "performance_findings", "run_id": "SYN-RUN-1", "period": copy.deepcopy(PERIOD),
            "status": status, "account": {"platform": "meta", "account_id": "SYN-ACC", "currency": "ILS"}, "coverage_gaps": ["CRM"],
            "findings": [{"finding_id": "F1", "claim": "Hook A had higher CTR than B", "kind": "observation", "metric": "ctr",
                          "evidence": [{"source_ref": "SYN-SRC-1", "entity_ids": {"account": "SYN-ACC", "campaign": "C1", "adset": None, "ad": "AD1", "creative": None}}]}],
            "actions": [{"action_id": "A1", "text": "Test a new hook", "evidence_refs": ["SYN-SRC-1"], "success_metric": "ctr", "status": "proposed"}]}


def _prop(pid, mapping="unresolved", hook=None):
    return {"proposal_id": pid, "status": "proposed_unapproved", "client_label": "SYN Client", "project_label": None,
            "mapping_status": mapping, "hook": hook or f"Synthetic hook {pid} about floor plan",
            "concept": f"Concept {pid}: compare two layouts", "primary_copy": "Synthetic copy", "cta": "Leave details",
            "opening_visual": "Floor plan reveal", "source_finding_ids": ["F1"], "source_refs": ["SYN-SRC-1"],
            "evidence": ["F1"], "hypotheses": ["layout curiosity drives clicks"],
            "approval_gates": {"fact": "pending", "production": "pending"}, "test": {"variable": "hook", "metric": "ctr"}}


def proposals(status="complete"):
    return {"schema_version": "1.0", "artifact": "creative_proposals", "run_id": "SYN-RUN-2", "period": copy.deepcopy(PERIOD),
            "status": status, "source_findings_run_id": "SYN-RUN-1",
            "proposals": [_prop("P1", hook="Alpha compare layouts"), _prop("P2", hook="Beta scale reveal", mapping="hypothesis"), _prop("P3", hook="Gamma materials close up")]}


def review(verdicts=("supported", "supported", "supported"), status="complete"):
    return {"schema_version": "1.0", "artifact": "evidence_review", "run_id": "SYN-RUN-3", "period": copy.deepcopy(PERIOD),
            "status": status, "proposals_run_id": "SYN-RUN-2",
            "reviews": [{"proposal_id": f"P{i+1}", "verdict": v, "unsupported_claims": [], "corrections": [], "evidence_refs": ["SYN-SRC-1"]} for i, v in enumerate(verdicts)]}


def task(i, title, status="todo", key=None, client="SYN Client", project="SYN Web"):
    return {"id": i, "title": title, "client": client, "project": project, "status": status, "approval_type": None, "revision": False,
            "due_date": None, "assignee": None, "created_at_local": "2025-12-01 09:00:00", "url": f"https://example.invalid/#task={i}",
            "external_task_key": key}


TF_OK = {"complete": True, "reported_count": 3, "fetched_count": 3, "issues": []}
