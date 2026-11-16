"""Synthetic integration/regression tests for handoff contracts and manager drafts. Offline."""
import copy, json, pathlib, subprocess, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts")); sys.path.insert(0, str(ROOT / "tests/fixtures"))
import handoff, manager_drafts as md, synthetic_handoff as fx, taskflow_client as tf

ok = True
def check(n, c):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + n)
build = lambda f=None, p=None, r=None, t=None, rd=None: md.build(f or fx.findings(), p or fx.proposals(), r or fx.review(), t or [], rd or fx.TF_OK, "2026-01-11")

# schema / version
for mk in (fx.findings, fx.proposals, fx.review):
    check(f"valid {mk.__name__}", handoff.validate(mk()) == [])
check("valid task_drafts", handoff.validate(build()) == [])
d = fx.findings(); d["schema_version"] = "2.0"
check("unsupported schema_version rejected", handoff.validate(d) != [])
d = fx.proposals(); del d["proposals"][0]["hook"]
check("missing required field rejected", any("hook" in e for e in handoff.validate(d)))
d = fx.proposals(); d["proposals"][0]["status"] = "approved"
check("self-approval rejected by schema", handoff.validate(d) != [])
d = fx.findings(); d["actions"] = d["actions"] * 6
check("more than 5 actions rejected", handoff.validate(d) != [])
d = fx.findings(); d["extra"] = 1
check("unexpected field rejected", handoff.validate(d) != [])
d = fx.findings(); d["findings"][0]["evidence"] = []
check("finding without evidence rejected", handoff.validate(d) != [])
out = build(); out["suggested"] = 1
check("task_drafts unknown field rejected", handoff.validate(out) != [])

# provenance
check("provenance ok", handoff.check_provenance(fx.findings(), fx.proposals(), fx.review()) == [])
p = fx.proposals(); p["proposals"][0]["source_refs"] = ["SYN-SRC-404"]
check("provenance: source_ref must exist in findings evidence", handoff.check_provenance(fx.findings(), p) != [])
p = fx.proposals(); p["proposals"][0]["source_finding_ids"] = ["F404"]
check("provenance: unknown finding id", handoff.check_provenance(fx.findings(), p) != [])
p = fx.proposals(); p["period"]["start"] = "2026-01-11"
check("provenance: period mismatch", handoff.check_provenance(fx.findings(), p) != [])
r = fx.review(); r["proposals_run_id"] = "OTHER"
check("provenance: review run mismatch", handoff.check_provenance(fx.findings(), fx.proposals(), r) != [])

# review gates
o = build(t=[fx.task(1, "Unrelated work")])
check("all supported -> 3 drafts, complete", len(o["drafts"]) == 3 and o["overall_status"] == "complete")
o = build(r=fx.review(("supported", "unsupported", "needs_correction")), t=[fx.task(1, "Unrelated work")])
check("unsupported/needs_correction blocked", [d["proposal_id"] for d in o["drafts"]] == ["P1"] and {b["proposal_id"] for b in o["blocked_proposals"]} == {"P2", "P3"})
check("blocked proposal => overall not complete", o["overall_status"] != "complete")
r = fx.review(); r["reviews"].pop()
o = build(r=r, t=[fx.task(1, "x")])
check("missing review blocks proposal", any(b["proposal_id"] == "P3" and "no evidence review" in b["reason"] for b in o["blocked_proposals"]))
for name, kw in (("partial findings", {"f": fx.findings("partial")}), ("partial proposals", {"p": fx.proposals("partial")}), ("partial review", {"r": fx.review(status="partial")})):
    o = build(t=[fx.task(1, "x")], **kw)
    check(f"{name} cannot yield complete overall", o["overall_status"] != "complete")
o = build(f=fx.findings("failed"), t=[fx.task(1, "x")])
check("failed upstream => overall failed", o["overall_status"] == "failed")
o = build(r=fx.review(status="failed"), t=[fx.task(1, "x")])
check("failed review step blocks all drafts", o["overall_status"] == "failed" and o["drafts"] == [])

# unresolved mapping / no guessed owner or deadline
o = build(t=[fx.task(1, "x")])
check("unresolved mapping preserved", next(d for d in o["drafts"] if d["proposal_id"] == "P1")["mapping_status"] == "unresolved")
check("hypothesis mapping preserved, never promoted", next(d for d in o["drafts"] if d["proposal_id"] == "P2")["mapping_status"] == "hypothesis")
check("no guessed owner/deadline; unapproved", all(d["suggested_owner"] is None and d["suggested_deadline"] is None and d["approval_status"] == "proposed_unapproved" for d in o["drafts"]))
check("project label not invented", all(d["project_label"] is None for d in o["drafts"]))

# duplicates
open_exact = fx.task(10, "Totally different title", key="SYN-SRC-1")
o = build(t=[open_exact])
check("exact source ref on open task => already represented, no new draft", len(o["already_represented"]) == 3 and o["drafts"] == [])
done_exact = fx.task(11, "Other", status="done", key="SYN-SRC-1")
o = build(t=[done_exact])
d0 = o["drafts"][0]
check("done task with same source: draft kept, flagged as historical only", len(o["drafts"]) == 3 and d0["duplicate_candidates"][0]["match"] == "exact_source_reference" and "historical" in d0["duplicate_candidates"][0]["reason"])
fuzzy = fx.task(12, "Alpha compare layouts floor plan hook")
o = build(t=[fuzzy])
p1 = next(d for d in o["drafts"] if d["proposal_id"] == "P1")
check("fuzzy title is a candidate, distinct from exact", p1["duplicate_candidates"] and p1["duplicate_candidates"][0]["match"] == "fuzzy_title" and not o["already_represented"])
check("related task URLs listed for candidates", p1["related_task_urls"] == [fuzzy["url"]])
other_client = fx.task(13, "Alpha compare layouts floor plan hook", client="Another Client")
o = build(t=[other_client])
check("fuzzy candidates stay within the same client", all(not d["duplicate_candidates"] for d in o["drafts"]))
wk = fx.task(14, "n/a", key="wk:2026-01-04:P2")
o = build(t=[wk])
check("weekly external key match => P2 already represented", [a["proposal_id"] for a in o["already_represented"]] == ["P2"])

# idempotency
tasks = [fx.task(1, "Alpha compare layouts floor plan hook"), done_exact]
a, b = build(t=copy.deepcopy(tasks)), build(t=copy.deepcopy(tasks))
check("idempotent: identical output on rerun", json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True))
check("draft ids and external keys stable", [d["draft_id"] for d in a["drafts"]] == [d["draft_id"] for d in b["drafts"]] and all(d["proposed_external_task_key"].startswith("wk:2026-01-04:") for d in a["drafts"]))
check("inputs not mutated", tasks[0] == fx.task(1, "Alpha compare layouts floor plan hook"))

# partial reads
o = build(t=[fx.task(1, "x")], rd={"complete": False, "reported_count": 406, "fetched_count": 300, "issues": ["incomplete: got 300 of 406"]})
check("partial TaskFlow read => failed, no drafts", o["overall_status"] == "failed" and o["drafts"] == [] and len(o["blocked_proposals"]) == 3 and handoff.validate(o) == [])

# blocked writes / safety
check("writes_performed is always 0", build(t=[fx.task(1, "x")])["writes_performed"] == 0)
for w in ("tasks.create", "tasks.update", "comments.add", "users.create"):
    try: tf.build_request(w); check(f"TaskFlow {w} blocked", False)
    except tf.TaskFlowError: check(f"TaskFlow {w} blocked", True)
src = (ROOT / "scripts/manager_drafts.py").read_text() + (ROOT / "scripts/handoff.py").read_text()
check("manager/handoff modules have no network/process access", not any(w in src for w in ("socket", "urllib", "requests", "http", "subprocess", "taskflow_client")))
al = json.loads((ROOT / "config/meta-allowlist.json").read_text())
check("Meta allowlist excludes every write prefix", not any(t.startswith(tuple(al["forbidden_prefixes"])) for t in al["allowed_tools"]))
check("Meta allowlist tools all read-style", all(t.startswith(("ads_get_", "ads_insights_")) for t in al["allowed_tools"]))

# git hygiene / registrations
ign = (ROOT / ".gitignore").read_text()
check(".gitignore covers runtime paths", "runtime/" in ign and "config/runtime/" in ign)
tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
check("no runtime artifacts tracked", not any(t.startswith(("runtime/", "config/runtime/")) for t in tracked))
check("no pilot account id in tracked files", all("408602783180027" not in (ROOT / t).read_text(errors="ignore") for t in tracked if (ROOT / t).is_file()))
def fm(n):
    t = (ROOT / f".claude/agents/{n}.md").read_text().split("---")[1]
    return dict(l.split(": ", 1) for l in t.strip().splitlines())
pa, ch, pm = fm("performance-analyst"), fm("copy-hooks"), fm("project-manager")
check("agent registrations: names", (pa["name"], ch["name"], pm["name"]) == ("performance-analyst", "copy-hooks", "project-manager"))
check("agent tools per spec", pa["tools"] == "Read, Glob, Grep, Write, Edit, Bash" and ch["tools"] == "Read, Glob, Grep, Write, Edit")
check("project-manager tools preserved", pm["tools"] == "Read, Grep, Glob, Bash")
sys.exit(0 if ok else 1)
