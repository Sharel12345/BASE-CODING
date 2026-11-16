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
sys.exit(0 if ok else 1)
