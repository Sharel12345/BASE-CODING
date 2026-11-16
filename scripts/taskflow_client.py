"""Read-only TaskFlow API v1 client (stdlib only).

Auth: Authorization: Bearer <TASKFLOW_API_KEY>; fallback header X-API-Key.
All calls: POST <base>?action=<action>, JSON UTF-8 body.
The key is read from the environment only and is never printed or logged.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://sitepass.goil.co.il/tasks/api/v1.php"
READ_ACTIONS = frozenset({"ping", "users.list", "clients.list", "projects.list", "tasks.list", "tasks.get"})
# Write actions per docs, blocked explicitly: users.create, tasks.create, tasks.update, comments.add.
# logs.recent is read-only but excluded: it echoes request bodies.


class TaskFlowError(Exception):
    pass


def call(action, body=None, *, base_url=BASE_URL, key=None, opener=None, timeout=30):
    if action not in READ_ACTIONS:
        raise TaskFlowError(f"action not allowed (read-only mode): {action}")
    key = key or os.environ.get("TASKFLOW_API_KEY")
    if not key:
        raise TaskFlowError("TASKFLOW_API_KEY is not set")
    url = f"{base_url}?{urllib.parse.urlencode({'action': action})}"
    data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": f"Bearer {key}",
    })
    try:
        resp = (opener or urllib.request.urlopen)(req, timeout=timeout)
        raw = resp.read()
    except urllib.error.HTTPError as e:
        raw = e.read()
    except urllib.error.URLError as e:
        raise TaskFlowError(f"network error: {e.reason}") from None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise TaskFlowError("non-JSON response") from None
    if not payload.get("ok"):
        raise TaskFlowError(str(payload.get("error", "unknown error")))
    return payload["data"]


def verify():
    """ping, then list counts. Prints no key and no record contents."""
    print("ping:", "ok", {k: v for k, v in call("ping").items() if "time" in k.lower()})
    for a in ("users.list", "clients.list", "projects.list", "tasks.list"):
        d = call(a)
        n = len(next((v for v in d.values() if isinstance(v, list)), [])) if isinstance(d, dict) else len(d)
        print(f"{a}: ok, {n} records")


if __name__ == "__main__":
    try:
        verify()
    except TaskFlowError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
