"""Offline pagination regression tests (fake transport, synthetic data)."""
import io, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import taskflow_client as tf

ok = True
def check(n, c):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + n)

def server(pages_fn, bodies):
    def op(req, timeout=0):
        body = json.loads(req.data.decode()); bodies.append(body)
        return io.BytesIO(json.dumps({"ok": True, "data": pages_fn(body.get("offset", 0))}).encode())
    return op

def make(total, size=2, count=None):
    items = [{"id": i} for i in range(1, total + 1)]
    return lambda off: {"tasks": items[off:off + size], "count": total if count is None else count}

b = []; r = tf.paginate("tasks.list", "tasks", opener=server(make(5), b))
check("multi-page read complete", r["complete"] and len(r["records"]) == 5 and r["requests"] == 3 and r["reported_count"] == 5)
check("limit never sent; offset-only", all("limit" not in x for x in b) and [x.get("offset", 0) for x in b] == [0, 2, 4])
b = []; r = tf.paginate("tasks.list", "tasks", opener=server(make(2), b))
check("single page", r["complete"] and r["requests"] == 1)
check("empty list is complete", tf.paginate("tasks.list", "tasks", opener=server(make(0), []))["complete"])
rep = lambda off: {"tasks": [{"id": 1}, {"id": 2}], "count": 10}
r = tf.paginate("tasks.list", "tasks", opener=server(rep, []))
check("repeated/non-advancing page -> incomplete, stops", not r["complete"] and r["requests"] == 2 and any("duplicate" in i for i in r["issues"]))
r = tf.paginate("tasks.list", "tasks", opener=server(lambda off: {"tasks": [{"id": 1}, {"id": 1}] if off == 0 else [], "count": 2}, []))
check("duplicate ids inside one page -> incomplete", not r["complete"] and any("duplicate" in i for i in r["issues"]))
short = lambda off: {"tasks": [{"id": 1}, {"id": 2}] if off == 0 else [], "count": 6}
r = tf.paginate("tasks.list", "tasks", opener=server(short, []))
check("early empty page -> incomplete read reported", not r["complete"] and any("got 2 of 6" in i for i in r["issues"]))
chg = lambda off: {"tasks": [{"id": off + 1}, {"id": off + 2}], "count": 4 if off == 0 else 5}
r = tf.paginate("tasks.list", "tasks", opener=server(chg, []))
check("changing count -> incomplete", not r["complete"] and any("count changed" in i for i in r["issues"]))
r = tf.paginate("tasks.list", "tasks", max_requests=2, opener=server(make(100), []))
check("finite request cap -> incomplete", not r["complete"] and r["requests"] == 2 and any("cap" in i for i in r["issues"]))
r = tf.paginate("tasks.list", "tasks", opener=server(lambda off: {"nope": 1}, []))
check("unexpected shape -> incomplete", not r["complete"])

# ---- catalog schemas observed live (synthetic values only) ----
def cat(key, rows, **extra):
    return lambda off: {key: rows[off:], "count": len(rows), **extra}
clients = [{"name": "SYN-Client-A", "open_tasks": 1, "tasks": 3}, {"name": "SYN-Client-B", "open_tasks": 0, "tasks": 1}]
r = tf.paginate("clients.list", opener=server(cat("clients", clients), []))
check("clients.list (no id field) reads complete by name identity", r["complete"] and len(r["records"]) == 2
      and r["identity_basis"] == {"fields": ["name"], "server_provided_id": False})
projects = [{"client": "SYN-Client-A", "name": "SYN-Proj", "open_tasks": 1, "tasks": 2},
            {"client": "SYN-Client-B", "name": "SYN-Proj", "open_tasks": 0, "tasks": 1}]
r = tf.paginate("projects.list", opener=server(cat("projects", projects, filtered_by_client=None), []))
check("same project name under different clients is NOT a duplicate", r["complete"] and len(r["records"]) == 2
      and r["identity_basis"]["fields"] == ["client", "name"] and not r["identity_basis"]["server_provided_id"])
r = tf.paginate("projects.list", opener=server(cat("projects", projects + [dict(projects[0])]), []))
check("same client+project repeated -> incomplete, not silently dropped", not r["complete"] and any("duplicate" in i for i in r["issues"]))
r = tf.paginate("projects.list", opener=server(cat("projects", [{"name": "SYN-P"}]), []))
check("project missing client -> incomplete (no guessed identity)", not r["complete"] and any("malformed" in i for i in r["issues"]))
r = tf.paginate("clients.list", opener=server(cat("clients", [{"name": "  "}]), []))
check("blank client name -> incomplete", not r["complete"])
r = tf.paginate("users.list", opener=server(cat("users", [{"id": 1, "name": "SYN-U", "color": "#fff", "open_tasks": 0}]), []))
check("users.list by id", r["complete"] and r["identity_basis"]["server_provided_id"])
r = tf.paginate("tasks.list", opener=server(lambda off: {"tasks": [{"id": 1}, {"title": "no id"}], "count": 2}, []))
check("task without id -> incomplete, strict validation kept", not r["complete"] and any("malformed" in i for i in r["issues"]))
r = tf.paginate("tasks.list", opener=server(lambda off: {"tasks": [{"id": None}], "count": 1}, []))
check("task id null -> incomplete", not r["complete"])
r = tf.paginate("tasks.list", opener=server(lambda off: {"tasks": [{"id": True}], "count": 1}, []))
check("task id bool -> incomplete", not r["complete"])
r = tf.paginate("tasks.list", opener=server(lambda off: {"tasks": ["x"], "count": 1}, []))
check("non-object record -> incomplete", not r["complete"])
r = tf.paginate("clients.list", opener=server(lambda off: {"clients": [], "count": 3}, []))
check("catalog reporting 3 but returning none -> incomplete", not r["complete"] and any("got 0 of 3" in i for i in r["issues"]))
r = tf.paginate("tasks.list", opener=server(lambda off: {"tasks": [{"id": 1}], "count": "1"}, []))
check("non-integer count -> incomplete", not r["complete"])
try:
    tf.paginate("tasks.get", opener=server(make(1), [])); raised = False
except tf.TaskFlowError:
    raised = True
check("action without explicit identity is refused", raised)
sys.exit(0 if ok else 1)
