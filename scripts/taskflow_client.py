"""Read-only TaskFlow API v1 client (stdlib only).

Auth modes (explicit; default is "proxy"):
  proxy: no credential is read or sent from Python. The managed network proxy
         (Claude cloud Network secrets) injects "Authorization: Bearer <secret>".
  env:   only when explicitly selected (TASKFLOW_AUTH_MODE=env or auth_mode="env");
         reads TASKFLOW_API_KEY and sends Authorization: Bearer. Key is never printed.
Endpoint is fixed: https://sitepass.goil.co.il/tasks/api/v1.php (no override, no redirects).
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HOST = "sitepass.goil.co.il"
PATH = "/tasks/api/v1.php"
ENDPOINT = f"https://{HOST}{PATH}"
READ_ACTIONS = frozenset({"ping", "users.list", "clients.list", "projects.list", "tasks.list", "tasks.get"})
# Blocked write actions: users.create, tasks.create, tasks.update, comments.add.
# logs.recent is read-only but excluded: it echoes request bodies.
AUTH_MODES = ("proxy", "env")


class TaskFlowError(Exception):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None  # redirects surface as HTTPError


def _default_open(req, timeout=30):
    return urllib.request.build_opener(_NoRedirect).open(req, timeout=timeout)


def _auth_mode(auth_mode):
    mode = auth_mode or os.environ.get("TASKFLOW_AUTH_MODE") or "proxy"
    if mode not in AUTH_MODES:
        raise TaskFlowError(f"unknown auth mode: {mode}")
    return mode


def build_request(action, body=None, auth_mode=None, key=None):
    if action not in READ_ACTIONS:
        raise TaskFlowError(f"action not allowed (read-only mode): {action}")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if _auth_mode(auth_mode) == "env":
        key = key or os.environ.get("TASKFLOW_API_KEY")
        if not key:
            raise TaskFlowError("env auth mode requires TASKFLOW_API_KEY")
        headers["Authorization"] = f"Bearer {key}"
    # proxy mode: deliberately no Authorization / X-API-Key header.
    url = f"{ENDPOINT}?{urllib.parse.urlencode({'action': action})}"
    data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8")
    return urllib.request.Request(url, data=data, method="POST", headers=headers)


def call(action, body=None, *, auth_mode=None, key=None, opener=None, timeout=30):
    req = build_request(action, body, auth_mode, key)
    try:
        raw = (opener or _default_open)(req, timeout=timeout).read()
    except urllib.error.HTTPError as e:
        if 300 <= e.code < 400:
            raise TaskFlowError("redirect refused") from None
        raw = e.read()
    except urllib.error.URLError as e:
        raise TaskFlowError(f"network error: {e.reason}") from None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise TaskFlowError("non-JSON response (possible missing proxy secret or blocked host)") from None
    if not payload.get("ok"):
        raise TaskFlowError(str(payload.get("error", "unknown error")))
    return payload["data"]


def verify(**kw):
    """ping, then list counts. Prints no secret and no record contents."""
    print("ping:", "ok", {k: v for k, v in call("ping", **kw).items() if "time" in k.lower()})
    for a in ("users.list", "clients.list", "projects.list", "tasks.list"):
        d = call(a, **kw)
        n = len(next((v for v in d.values() if isinstance(v, list)), [])) if isinstance(d, dict) else len(d)
        print(f"{a}: ok, {n} records")


if __name__ == "__main__":
    try:
        verify()
    except TaskFlowError as e:
        print(f"FAILED: {e}")
        sys.exit(1)
