import json, pathlib, sys, copy
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from analyze import analyze

FX = ROOT / "tests" / "fixtures"
snap = json.loads((FX / "synthetic_snapshot.json").read_text())
props = json.loads((FX / "synthetic_proposals.json").read_text())["proposals"]
before = copy.deepcopy((snap, props))
r = analyze(snap, props, "2026-01-15")
results = []
def check(name, cond): results.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name)

check("overdue task detected (SYN-T1)", [x["task_id"] for x in r["overdue"]] == ["SYN-T1"])
check("awaiting client approval detected (SYN-T2)", [x["task_id"] for x in r["awaiting_approval"]] == ["SYN-T2"])
check("no-owner task detected (SYN-T3)", [x["task_id"] for x in r["no_owner"]] == ["SYN-T3"])
check("stale task not marked blocked (SYN-T4)", r["blocked"] == [])
check("existing-task recommendation deduped (SYN-PR1 -> SYN-T4)", r["duplicates"] == [{"proposal_id": "SYN-PR1", "existing_task_id": "SYN-T4"}])
titles = [p["title"] for p in r["proposals"]]
check("no duplicate proposal emitted", "Prepare the monthly report" not in titles and len(titles) == 2)
creative = next(p for p in r["proposals"] if p["title"].startswith("Idea"))
check("creative idea stays unapproved", creative["approval_status"] == "proposed_unapproved")
check("no invented assignee/deadline", all(p["suggested_assignee_id"] is None and p["suggested_due_date"] is None for p in r["proposals"]))
check("proposal has all required fields", all({"title","description","client_id","project_id","suggested_assignee_id","suggested_due_date","priority","source_reference","approval_status"} <= p.keys() for p in r["proposals"]))
check("inputs not mutated", (snap, props) == before)
src = (ROOT / "scripts" / "analyze.py").read_text()
check("no network/write capability in analyzer", not any(w in src for w in ("socket", "urllib", "requests", "http", "open(", "subprocess")))
sj = json.loads((ROOT / "config" / "sources.json").read_text())
check("TaskFlow not falsely marked connected", sj["taskflow"]["status"] != "connected" and sj["taskflow"]["verification"]["last_verified"] is None)
check("sources.json contains no secret values", not any(k in json.dumps(sj) for k in ("Bearer ey", "sk-")))
sys.exit(0 if all(ok for _, ok in results) else 1)
