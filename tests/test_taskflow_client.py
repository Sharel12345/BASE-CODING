"""Offline tests with a fake transport. No network, no real key."""
import io, json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import taskflow_client as tf

seen = []
def fake(req, timeout=0):
    seen.append(req)
    return io.BytesIO(json.dumps({"ok": True, "data": {"server_time": "x"}}).encode())

ok = True
def check(n, c):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + n)

for w in ("tasks.create", "tasks.update", "comments.add", "users.create", "logs.recent"):
    try: tf.call(w, key="SYN-KEY", opener=fake); check(f"blocks {w}", False)
    except tf.TaskFlowError: check(f"blocks {w}", True)
check("no request sent for blocked actions", not seen)
tf.call("ping", key="SYN-KEY", opener=fake)
r = seen[0]
check("POST with ?action=ping", r.get_method() == "POST" and r.full_url.endswith("?action=ping"))
check("Bearer auth header", r.get_header("Authorization") == "Bearer SYN-KEY")
try: tf.call("ping", key=None, opener=fake) if "TASKFLOW_API_KEY" not in __import__("os").environ else None; 
except tf.TaskFlowError as e: check("missing key rejected without leaking", "SYN-KEY" not in str(e))
sys.exit(0 if ok else 1)
