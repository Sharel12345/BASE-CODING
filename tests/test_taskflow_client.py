"""Offline tests with a fake transport. No network, no real key."""
import io, json, os, pathlib, sys, urllib.error
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import taskflow_client as tf

os.environ.pop("TASKFLOW_API_KEY", None); os.environ.pop("TASKFLOW_AUTH_MODE", None)
seen = []
def fake(req, timeout=0):
    seen.append(req)
    return io.BytesIO(json.dumps({"ok": True, "data": {"server_time": "x"}}).encode())

ok = True
def check(n, c):
    global ok; ok &= bool(c); print(("PASS " if c else "FAIL ") + n)
def raises(f):
    try: f(); return False
    except tf.TaskFlowError: return True

# proxy mode (default)
tf.call("ping", opener=fake)
h = {k.lower() for k in seen[-1].headers}
check("default mode is proxy and works with no env key", True)
check("proxy mode sends no Authorization / X-API-Key", "authorization" not in h and "x-api-key" not in h)
check("proxy mode ignores a present env key", (os.environ.__setitem__("TASKFLOW_API_KEY", "SYN-KEY"), tf.call("ping", opener=fake), "authorization" not in {k.lower() for k in seen[-1].headers})[2])
os.environ.pop("TASKFLOW_API_KEY")
# env mode
check("env mode without key fails", raises(lambda: tf.call("ping", auth_mode="env", opener=fake)))
tf.call("ping", auth_mode="env", key="SYN-KEY", opener=fake)
check("env mode sends Bearer", seen[-1].get_header("Authorization") == "Bearer SYN-KEY")
os.environ["TASKFLOW_AUTH_MODE"] = "env"
check("TASKFLOW_AUTH_MODE=env selects env mode", raises(lambda: tf.call("ping", opener=fake)))
os.environ.pop("TASKFLOW_AUTH_MODE")
check("unknown mode rejected", raises(lambda: tf.call("ping", auth_mode="x", opener=fake)))
# endpoint binding
r = seen[0]
check("fixed HTTPS host/path, POST, ?action=", r.full_url == "https://sitepass.goil.co.il/tasks/api/v1.php?action=ping" and r.get_method() == "POST")
check("no endpoint override parameter", "base_url" not in tf.call.__code__.co_varnames and "url" not in tf.call.__code__.co_varnames)
# writes blocked, nothing sent
n = len(seen)
for w in ("tasks.create", "tasks.update", "comments.add", "users.create", "logs.recent", "ping2"):
    check(f"blocks {w} in both modes", raises(lambda: tf.call(w, opener=fake)) and raises(lambda: tf.call(w, auth_mode="env", key="k", opener=fake)))
check("no request sent for blocked actions", len(seen) == n)
# redirects
def redir(req, timeout=0): raise urllib.error.HTTPError(req.full_url, 302, "Found", {}, io.BytesIO(b""))
check("redirect refused", raises(lambda: tf.call("ping", opener=redir)))
import urllib.request
check("default opener disallows redirects", tf._NoRedirect().redirect_request(None, None, 302, "", {}, "http://evil/") is None)
# no secret leakage
src = (ROOT / "scripts" / "taskflow_client.py").read_text()
check("client never prints key or sends X-API-Key", "print(key" not in src and "headers[\"X-API-Key\"]" not in src)
sj = json.loads((ROOT / "config" / "sources.json").read_text())["taskflow"]
check("sources.json: proxy mode, not marked connected", sj["auth_mode"] == "proxy" and sj["status"] == "configured_unverified" and sj["verification"]["last_verified"] is None)
sys.exit(0 if ok else 1)
