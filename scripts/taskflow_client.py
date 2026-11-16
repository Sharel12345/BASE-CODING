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


MAX_REQUESTS = 40  # finite cap on pages per paginated read


# Explicit per-action record identity. Observed live shapes (synthetic tests mirror them):
#   users.list    {users:[{id,name,color,open_tasks}], count}                      -> id
#   clients.list  {clients:[{name,open_tasks,tasks}], count}                       -> NO id; name
#   projects.list {projects:[{client,name,open_tasks,tasks}], count,
#                  filtered_by_client}                                             -> NO id; (client, name)
#   tasks.list    {tasks:[{id,...}], count, limit, offset}                         -> id (strict)
# Names/composite keys are unverified matching aids, NEVER stable IDs: the server exposes none for
# clients/projects, and the same project name legitimately exists under different clients.
IDENTITY = {
    "tasks.list": ("id",),
    "users.list": ("id",),
    "clients.list": ("name",),
    "projects.list": ("client", "name"),
}
LIST_KEYS = {"tasks.list": "tasks", "users.list": "users", "clients.list": "clients", "projects.list": "projects"}


def _identity(rec, fields):
    """Return the record's identity tuple or None when malformed (missing/empty/non-scalar part)."""
    if not isinstance(rec, dict):
        return None
    out = []
    for f in fields:
        v = rec.get(f)
        if isinstance(v, bool) or v is None or not isinstance(v, (str, int)) or (isinstance(v, str) and not v.strip()):
            return None
        out.append(v)
    return tuple(out)


def paginate(action, list_key=None, *, id_key=None, id_fields=None, max_requests=MAX_REQUESTS, **kw):
    """Offset-only pagination (never sends `limit`; the server rejects it with 403).

    Record identity is explicit per action (see IDENTITY); `id_fields`/`id_key` override it.
    Returns {records, complete, reported_count, requests, issues, identity_basis}. Never raises on
    incompleteness: callers must check `complete` and report `issues`. Malformed records (missing
    identity), duplicate identities, repeated pages, changing counts and short reads all make the
    result incomplete; nothing is silently dropped.
    """
    fields = tuple(id_fields) if id_fields else ((id_key,) if id_key else IDENTITY.get(action))
    list_key = list_key or LIST_KEYS.get(action)
    if not fields or not list_key:
        raise TaskFlowError(f"no explicit record identity/list key defined for action: {action}")
    records, seen, issues = [], set(), []
    reported, offset, requests = None, 0, 0
    while True:
        if requests >= max_requests:
            issues.append("request cap reached")
            break
        body = {"offset": offset} if offset else {}
        data = call(action, body, **kw)
        requests += 1
        page = data.get(list_key) if isinstance(data, dict) else None
        if not isinstance(page, list) or isinstance(data.get("count"), bool) or not isinstance(data.get("count"), int):
            issues.append("unexpected response shape")
            break
        if reported is not None and data["count"] != reported:
            issues.append(f"count changed during read: {reported} -> {data['count']}")
            reported = data["count"]
        reported = data["count"] if reported is None else reported
        if not page:
            break
        ids = [_identity(r, fields) for r in page]
        bad = sum(1 for i in ids if i is None)
        if bad:
            issues.append(f"malformed records without identity {'+'.join(fields)}: {bad}")
            break  # never skip/guess: the page is unusable, the read is incomplete
        dup = [i for i in ids if i in seen] + [i for i in set(ids) if ids.count(i) > 1]
        if dup:
            issues.append(f"duplicate ids returned: {len(dup)}")
            break  # repeated/non-advancing page or duplicates within a page
        seen.update(ids)
        records.extend(page)
        offset += len(page)
        if offset >= reported:
            break
    if len(records) != reported:
        issues.append(f"incomplete: got {len(records)} of {reported}")
    return {"records": records, "complete": not issues, "reported_count": reported,
            "requests": requests, "issues": issues,
            "identity_basis": {"fields": list(fields), "server_provided_id": fields == ("id",)}}


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
