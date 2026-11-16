import json, pathlib, sys, copy, datetime as dt
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from analyze import analyze, israel_today, TZ

fx = json.loads((ROOT / "tests/fixtures/synthetic_tasks.json").read_text())
tasks, props = fx["tasks"], fx["proposals"]
before = copy.deepcopy((tasks, props))
r = analyze(tasks, props, "2026-01-15")
ids = lambda k: sorted(x["task_id"] for x in r[k])
ok = True
def check(n, c):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + n)

check("totals use open tasks only (9 open, 1 done)", r["totals"] == {"all": 10, "open": 9, "done": 1})
check("overdue = open past-due only (done task excluded)", ids("overdue") == [1])
check("due today is not overdue", ids("due_today") == [2] and 2 not in ids("overdue"))
check("upcoming within 3 days", ids("upcoming") == [3])
check("missing deadline distinct from overdue", ids("no_due_date") == [4, 6, 7, 10] and not set(ids("no_due_date")) & set(ids("overdue")))
check("no-owner via assignee None (done excluded)", ids("no_owner") == [7])
check("client approval detected", ids("awaiting_client_approval") == [4])
check("manager approval detected", ids("awaiting_manager_approval") == [5])
check("approval without type reported separately", ids("approval_untyped") == [6])
check("revision flag reported", ids("revision") == [9])
check("no blockers inferred from stale/old tasks", r["blocked"] == [])
check("time in approval never inferred from created date", r["time_in_approval"].startswith("unknown") and all("days_in_approval" not in x for x in r["awaiting_client_approval"]))
check("name mapping marked unverified", r["mapping"] == {"basis": "names_only", "verified": False})
check("ambiguous client spelling flagged", any(a["field"] == "client" and len(a["variants"]) == 2 for a in r["ambiguous_names"]))
check("existing-task proposal deduped (source key + title)", r["duplicates"] == [{"proposal_id": "SYN-PR1", "existing_task_id": 9}])
check("same title in other client/project is NOT a duplicate", "Overdue banner" in [p["title"] for p in r["proposals"]])
check("2 + 1 proposals remain besides duplicate", len(r["proposals"]) == 3)
c = next(p for p in r["proposals"] if p["title"].startswith("Idea"))
check("creative idea stays unapproved", c["approval_status"] == "proposed_unapproved")
check("no invented ids/assignee/deadline", all(p["client_id"] is None and p["project_id"] is None and p["suggested_assignee_id"] is None and p["suggested_due_date"] is None for p in r["proposals"]))
check("proposal has required fields", all({"title","description","client_id","project_id","suggested_assignee_id","suggested_due_date","priority","source_reference","approval_status"} <= p.keys() for p in r["proposals"]))
check("inputs not mutated", (tasks, props) == before)
utc = dt.datetime(2026, 1, 14, 22, 30, tzinfo=dt.timezone.utc)  # 00:30 Jan 15 in Israel
check("Israel local date used (UTC 22:30 -> next day)", israel_today(utc) == dt.date(2026, 1, 15))
src = (ROOT / "scripts/analyze.py").read_text()
check("analyzer has no network/file/process access", not any(w in src for w in ("socket", "urllib", "requests", "http", "open(", "subprocess")))
sj = json.loads((ROOT / "config/sources.json").read_text())
check("sources.json holds no secret values", not any(k in json.dumps(sj) for k in ("Bearer ey", "sk-")))
sys.exit(0 if ok else 1)
